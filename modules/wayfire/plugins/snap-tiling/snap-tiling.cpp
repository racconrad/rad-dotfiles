#include "hud.hpp"
#include "placement.hpp"
#include "selection.hpp"
#include <wayfire/per-output-plugin.hpp>
#include <wayfire/output.hpp>
#include <wayfire/render-manager.hpp>
#include <wayfire/toplevel-view.hpp>
#include <wayfire/workarea.hpp>
#include <wayfire/plugins/common/input-grab.hpp>
#include <wayfire/seat.hpp>
#include <wayfire/signal-definitions.hpp>
#include <linux/input-event-codes.h>
#include <xkbcommon/xkbcommon.h>

class snap_output : public wf::per_output_plugin_instance_t,
    public wf::keyboard_interaction_t, public wf::pointer_interaction_t
{
    std::unique_ptr<wf::input_grab_t> grab;
    std::unique_ptr<snap::placement_controller> placement;
    std::weak_ptr<wf::toplevel_view_interface_t> target;
    snap::selector_view hud;
    unsigned pattern = 0, slot = 0;
    bool visible = false, outside_press = false;
    std::optional<std::pair<unsigned, unsigned>> pressed;
    wf::plugin_activation_data_t activation;
    wf::option_wrapper_t<wf::keybinding_t> toggle_option{"snap-tiling/toggle"};
    wf::option_wrapper_t<wf::keybinding_t> restore_option{"snap-tiling/detach"};
    wf::option_wrapper_t<int> gap_option{"snap-tiling/gap"};

    bool binding_pressed(wf::seat_t *seat, const wlr_keyboard_key_event& event,
        const wf::keybinding_t& binding) const
    {
        auto state = seat->get_xkb_state();
        if (!state) return false;
        auto symbol = xkb_state_key_get_one_sym(state, event.keycode + 8);
        return wf::keybinding_t(seat->get_keyboard_modifiers(), symbol) == binding;
    }

    snap::box workarea() const
    {
        auto area = output->workarea->get_workarea();
        return {int(area.x), int(area.y), int(area.width), int(area.height)};
    }

    snap::selector_layout selector() const { return snap::selector_layout(workarea()); }

    std::vector<snap::box> slots() const
    {
        return snap::layout(workarea(), pattern, std::clamp(int(gap_option), 0, 100));
    }

    void redraw()
    {
        auto cells = slots();
        if (cells.empty()) return;
        slot %= cells.size();
        auto error = placement->can_place(target.lock(), cells[slot]);
        hud.set_selection(pattern, slot, error);
        output->render->damage_whole();
    }

    void close()
    {
        if (!visible) return;
        visible = false;
        pressed.reset();
        outside_press = false;
        if (grab->is_grabbed()) grab->ungrab_input();
        output->deactivate_plugin(&activation);
        target.reset();
        hud.clear();
        output->render->damage_whole();
    }

    void apply()
    {
        if (!selector().usable()) return;
        auto cells = slots();
        if (cells.empty()) return;
        auto error = placement->place(target.lock(), cells[slot % cells.size()]);
        if (error.empty()) close();
        else { hud.set_selection(pattern, slot, error); output->render->damage_whole(); }
    }

    wf::key_callback toggle = [this] (const wf::keybinding_t&)
    {
        if (visible) { close(); return true; }
        auto view = wf::toplevel_cast(wf::get_active_view_for_output(output));
        if (!view || !view->is_mapped() || view->parent || view->pending_fullscreen()) return false;
        if (!output->activate_plugin(&activation)) return false;
        target = view->weak_from_this();
        visible = true;
        slot = 0;
        grab->set_wants_raw_input(true);
        grab->grab_input(wf::scene::layer::OVERLAY);
        redraw();
        return true;
    };
    wf::key_callback restore = [this] (const wf::keybinding_t&)
    {
        auto view = target.lock();
        if (!visible)
        {
            auto active = wf::toplevel_cast(wf::get_active_view_for_output(output));
            view = active ? active->shared_from_this() : nullptr;
        }
        close();
        return placement->restore(view);
    };
    wf::signal::connection_t<wf::view_disappeared_signal> disappeared = [this] (auto *event)
    {
        if (target.lock().get() == event->view.get()) close();
    };
    wf::signal::connection_t<wf::output_gain_focus_signal> output_focus = [this] (auto *event)
    {
        if (event->output != output) close();
    };
    wf::signal::connection_t<wf::workspace_changed_signal> workspace = [this] (auto*) { close(); };
    wf::signal::connection_t<wf::workspace_set_changed_signal> workspace_set = [this] (auto*) { close(); };
    wf::signal::connection_t<wf::workarea_changed_signal> area_changed = [this] (auto*) { if (visible) redraw(); };
    wf::effect_hook_t paint = [this]
    {
        if (!visible) return;
        auto pass = output->render->get_current_pass();
        if (!pass) return;
        auto cells = slots();
        if (cells.empty()) { close(); return; }
        auto cell = cells[slot % cells.size()];
        if (selector().usable() && placement->can_place(target.lock(), cell).empty())
        {
            wf::geometry_t rectangle{double(cell.x), double(cell.y), double(cell.width), double(cell.height)};
            pass->add_rect({.56, .70, .95, .12}, pass->get_target(), rectangle, wf::regionf_t{rectangle});
            for (auto edge : {wf::geometry_t{rectangle.x, rectangle.y, rectangle.width, 2},
                {rectangle.x, rectangle.y + rectangle.height - 2, rectangle.width, 2},
                {rectangle.x, rectangle.y, 2, rectangle.height},
                {rectangle.x + rectangle.width - 2, rectangle.y, 2, rectangle.height}})
                pass->add_rect({.62, .75, .97, .65}, pass->get_target(), edge, wf::regionf_t{edge});
        }
        hud.render(*pass, selector());
    };

  public:
    void init() override
    {
        placement = std::make_unique<snap::placement_controller>(output);
        activation.name = "snap-tiling";
        activation.capabilities = wf::CAPABILITY_GRAB_INPUT;
        activation.cancel = [this] { close(); };
        grab = std::make_unique<wf::input_grab_t>("snap-selector", output, this, this);
        output->add_key(toggle_option, &toggle);
        output->add_key(restore_option, &restore);
        output->connect(&disappeared);
        output->connect(&workspace);
        output->connect(&workspace_set);
        output->connect(&area_changed);
        wf::get_core().connect(&output_focus);
        output->render->add_effect(&paint, wf::OUTPUT_EFFECT_OVERLAY);
    }

    void handle_keyboard_key(wf::seat_t*, wlr_keyboard_key_event event) override
    {
        if (!visible || event.state != WL_KEYBOARD_KEY_STATE_PRESSED) return;
        auto *seat = wf::get_core().seat.get();
        if (binding_pressed(seat, event, toggle_option)) { close(); return; }
        if (binding_pressed(seat, event, restore_option))
        {
            auto view = target.lock();
            close();
            placement->restore(view);
            return;
        }
        switch (event.keycode)
        {
          case KEY_ESC: close(); return;
          case KEY_ENTER: case KEY_KPENTER: apply(); return;
          case KEY_TAB:
            pattern = (pattern + ((seat->get_keyboard_modifiers() & WLR_MODIFIER_SHIFT) ? 5 : 1)) % 6;
            slot = 0;
            break;
          case KEY_LEFT: case KEY_UP: case KEY_RIGHT: case KEY_DOWN:
            slot = snap::select_direction(slots(), slot,
                event.keycode == KEY_LEFT ? -1 : (event.keycode == KEY_RIGHT ? 1 : 0),
                event.keycode == KEY_UP ? -1 : (event.keycode == KEY_DOWN ? 1 : 0));
            break;
          default:
            if (event.keycode < KEY_1 || event.keycode > KEY_6) return;
            pattern = event.keycode - KEY_1; slot = 0;
        }
        redraw();
    }

    void handle_pointer_motion(wf::pointf_t, uint32_t) override
    {
        if (!visible) return;
        auto position = wf::get_core().get_cursor_position() - wf::origin(output->get_layout_geometry());
        if (auto hit = selector().hit(position.x, position.y))
        {
            if (pattern == hit->first && slot == hit->second) return;
            pattern = hit->first; slot = hit->second; redraw();
        }
    }

    void handle_pointer_button(const wlr_pointer_button_event& event) override
    {
        if (!visible || event.button != BTN_LEFT) return;
        auto position = wf::get_core().get_cursor_position() - wf::origin(output->get_layout_geometry());
        auto ui = selector();
        if (event.state == WL_POINTER_BUTTON_STATE_PRESSED)
        {
            pressed = ui.hit(position.x, position.y);
            outside_press = !ui.contains(position.x, position.y);
        } else
        {
            if (outside_press) { close(); return; }
            auto released = ui.hit(position.x, position.y);
            if (pressed && released == pressed)
            { pattern = pressed->first; slot = pressed->second; pressed.reset(); apply(); }
            else pressed.reset();
        }
    }

    void fini() override
    {
        close();
        disappeared.disconnect(); workspace.disconnect(); workspace_set.disconnect();
        area_changed.disconnect(); output_focus.disconnect();
        output->rem_binding(&toggle);
        output->rem_binding(&restore);
        output->render->rem_effect(&paint);
        grab.reset();
        placement.reset();
    }
};
DECLARE_WAYFIRE_PLUGIN(wf::per_output_plugin_t<snap_output>);
