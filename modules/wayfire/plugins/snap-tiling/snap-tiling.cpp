#include "layout.hpp"
#include "gestures.hpp"
#include "divider.hpp"
#include "group.hpp"
#include <wayfire/signal-definitions.hpp>
#include <wayfire/per-output-plugin.hpp>
#include <wayfire/output.hpp>
#include <wayfire/render-manager.hpp>
#include <wayfire/render.hpp>
#include <wayfire/toplevel-view.hpp>
#include <wayfire/workarea.hpp>
#include <wayfire/workspace-set.hpp>
#include <wayfire/txn/transaction-manager.hpp>
#include <wayfire/plugins/common/input-grab.hpp>
#include <linux/input-event-codes.h>
#include <map>
#include <wayfire/plugins/common/move-drag-interface.hpp>
#include <wayfire/plugins/common/shared-core-data.hpp>
#include <wayfire/option-wrapper.hpp>

class snap_output : public wf::per_output_plugin_instance_t,
    public wf::keyboard_interaction_t
{
    std::unique_ptr<wf::input_grab_t> grab;
    std::weak_ptr<wf::toplevel_view_interface_t> target;
    unsigned pattern = 0, selected = 0;
    bool visible = false;
    wf::plugin_activation_data_t activation;
    wf::shared_data::ref_ptr_t<wf::move_drag::core_drag_t> drag;
    bool drag_preview = false;
    std::unique_ptr<snap::gestures> gestures;
    std::unique_ptr<snap::divider> divider;
    std::unique_ptr<snap::group_controller> groups;
    wf::option_wrapper_t<wf::keybinding_t> toggle_option{"snap-tiling/toggle"};
    wf::signal::connection_t<wf::move_drag::drag_motion_signal> drag_motion = [this] (wf::move_drag::drag_motion_signal *event)
    {
        if (grab->is_grabbed()) return;
        auto area = output->get_layout_geometry();
        auto position = event->current_position;
        if (drag->current_output != output || !drag->view || position.y < area.y ||
            position.y > area.y + 25 || position.x < area.x || position.x >= area.x + area.width)
        {
            if (drag_preview) close();
            return;
        }
        if (drag->view->parent || drag->view->pending_fullscreen()) return;
        drag_preview = visible = true;
        target = drag->view->weak_from_this();
        auto workarea = output->workarea->get_workarea();
        auto cells = snap::layout({int(workarea.x), int(workarea.y), int(workarea.width), int(workarea.height)}, pattern);
        if (!cells.empty()) selected = std::min(unsigned(cells.size() - 1), unsigned((position.x - area.x) * cells.size() / area.width));
        output->render->damage_whole();
    };
    wf::signal::connection_t<wf::move_drag::drag_done_signal> drag_done = [this] (wf::move_drag::drag_done_signal *event)
    {
        if (!drag_preview) return;
        if (event->focused_output == output && event->main_view && event->main_view->is_mapped()) apply();
        else close();
    };
    wf::key_callback toggle = [this] (const wf::keybinding_t&)
    {
        if (visible) close();
        else
        {
            auto view = wf::toplevel_cast(wf::get_active_view_for_output(output));
            if (!view || view->parent || view->pending_fullscreen()) return false;
            if (!output->activate_plugin(&activation)) return false;
            target = view->weak_from_this();
            visible = true;
            selected = 0;
            grab->grab_input(wf::scene::layer::OVERLAY);
            output->render->damage_whole();
        }
        return true;
    };
    wf::effect_hook_t paint = [this]
    {
        if (!visible) return;
        auto pass = output->render->get_current_pass();
        if (!pass) return;
        auto area = output->workarea->get_workarea();
        auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern, 10, pattern == groups->group_pattern ? groups->ratio : -1);
        auto render_target = pass->get_target();
        for (unsigned i = 0; i < cells.size(); ++i)
        {
            auto b = cells[i];
            wf::geometry_t rect{double(b.x + 8), double(b.y + 8), double(std::max(1, b.width - 16)), double(std::max(1, b.height - 16))};
            pass->add_rect(i == selected ? wf::color_t{0.25, 0.65, 0.95, 0.38} :
                wf::color_t{0.1, 0.12, 0.15, 0.18}, render_target, rect, wf::regionf_t{rect});
        }
    };

    void close()
    {
        visible = false;
        drag_preview = false;
        if (grab->is_grabbed()) grab->ungrab_input();
        output->deactivate_plugin(&activation);
        target.reset();
        output->render->damage_whole();
    }

    void apply()
    {
        auto view = target.lock();
        if (!view || !view->is_mapped() || view->get_output() != output) { close(); return; }
        groups->place(view, pattern, selected);
        close();
    }

  public:
    void init() override
    {
        groups = std::make_unique<snap::group_controller>(output);
        gestures = std::make_unique<snap::gestures>(output);
        divider = std::make_unique<snap::divider>(output,
            [this] (wf::pointf_t point) { return !visible && groups->divider_hit(point); },
            [this] (wf::pointf_t point) { groups->divider_move(point); });
        activation.name = "snap-tiling";
        activation.capabilities = wf::CAPABILITY_GRAB_INPUT;
        activation.cancel = [this] { close(); };
        drag->connect(&drag_motion);
        drag->connect(&drag_done);
        grab = std::make_unique<wf::input_grab_t>("snap-tiling", output, this);
        output->add_key(toggle_option, &toggle);
        for (auto code : {KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN})
        {
            output->add_key(std::make_shared<wf::config::option_t<wf::keybinding_t>>("snap-tiling/resize",
                wf::keybinding_t{WLR_MODIFIER_LOGO | WLR_MODIFIER_ALT, uint32_t(code)}), &groups->resize);
            output->add_key(std::make_shared<wf::config::option_t<wf::keybinding_t>>("snap-tiling/focus",
                wf::keybinding_t{WLR_MODIFIER_LOGO, uint32_t(code)}), &groups->focus);
        }
        output->add_key(std::make_shared<wf::config::option_t<wf::keybinding_t>>("snap-tiling/detach",
            wf::keybinding_t{WLR_MODIFIER_LOGO | WLR_MODIFIER_SHIFT, KEY_SPACE}), &groups->detach);
        output->render->add_effect(&paint, wf::OUTPUT_EFFECT_OVERLAY);
    }

    void handle_keyboard_key(wf::seat_t*, wlr_keyboard_key_event event) override
    {
        if (event.state != WL_KEYBOARD_KEY_STATE_PRESSED) return;
        switch (event.keycode)
        {
          case KEY_ESC: close(); return;
          case KEY_ENTER: apply(); return;
          case KEY_LEFT: case KEY_UP:
          {
              auto area = output->workarea->get_workarea();
              auto count = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern).size();
              if (count) selected = (selected + count - 1) % count;
              break;
          }
          case KEY_RIGHT: case KEY_DOWN: ++selected; break;
          case KEY_TAB: pattern = (pattern + 1) % 6; selected = 0; break;
          default:
            if (event.keycode >= KEY_1 && event.keycode <= KEY_6)
            { pattern = event.keycode - KEY_1; selected = 0; }
            else return;
        }
        auto area = output->workarea->get_workarea();
        auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern);
        if (!cells.empty()) selected %= cells.size();
        output->render->damage_whole();
    }

    void fini() override
    {
        close();
        drag_motion.disconnect();
        drag_done.disconnect();
        output->rem_binding(&toggle);
        output->rem_binding(&groups->resize);
        output->rem_binding(&groups->focus);
        output->rem_binding(&groups->detach);
        output->render->rem_effect(&paint);
        grab.reset();
        gestures.reset();
        divider.reset();
        groups.reset();
    }
};
DECLARE_WAYFIRE_PLUGIN(wf::per_output_plugin_t<snap_output>);
