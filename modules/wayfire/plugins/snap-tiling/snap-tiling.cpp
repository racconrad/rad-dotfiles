#include "layout.hpp"
#include "selection.hpp"
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
    std::vector<std::unique_ptr<wf::option_wrapper_t<wf::keybinding_t>>> bindings;
    wf::option_wrapper_t<int> threshold{"snap-tiling/threshold"};
    wf::option_wrapper_t<wf::keybinding_t> toggle_option{"snap-tiling/toggle"};
    wf::signal::connection_t<wf::move_drag::drag_motion_signal> drag_motion = [this] (wf::move_drag::drag_motion_signal *event)
    {
        if (grab->is_grabbed()) return;
        auto area = output->get_layout_geometry();
        auto position = event->current_position;
        if (drag->current_output != output || !drag->view || position.y < area.y ||
            (!drag_preview && position.y > area.y + std::clamp(int(threshold), 1, 200)) ||
            position.y >= area.y + area.height || position.x < area.x || position.x >= area.x + area.width)
        {
            if (drag_preview) close();
            return;
        }
        if (drag->view->parent || drag->view->pending_fullscreen()) return;
        drag_preview = visible = true;
        target = drag->view->weak_from_this();
        auto workarea = output->workarea->get_workarea();
        auto cells = snap::layout({int(workarea.x), int(workarea.y), int(workarea.width), int(workarea.height)}, pattern, groups->gap(), pattern == groups->group_pattern ? groups->ratio : -1);
        if (!cells.empty()) selected = snap::select_at(cells, position.x - area.x, position.y - area.y);
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
        auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern, groups->gap(), pattern == groups->group_pattern ? groups->ratio : -1);
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

    void add_binding(const std::string& name, wf::key_callback* callback)
    {
        auto option = std::make_unique<wf::option_wrapper_t<wf::keybinding_t>>("snap-tiling/" + name);
        output->add_key(*option, callback);
        bindings.push_back(std::move(option));
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
        const char* directions[] = {"left", "right", "up", "down"};
        for (auto direction : directions)
        {
            add_binding(std::string("focus_") + direction, &groups->focus);
            add_binding(std::string("resize_") + direction, &groups->resize);
        }
        add_binding("detach", &groups->detach);
        output->render->add_effect(&paint, wf::OUTPUT_EFFECT_OVERLAY);
    }

    void handle_keyboard_key(wf::seat_t*, wlr_keyboard_key_event event) override
    {
        if (event.state != WL_KEYBOARD_KEY_STATE_PRESSED) return;
        switch (event.keycode)
        {
          case KEY_ESC: close(); return;
          case KEY_ENTER: apply(); return;
          case KEY_LEFT: case KEY_UP: case KEY_RIGHT: case KEY_DOWN:
          {
              auto area = output->workarea->get_workarea();
              auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern, groups->gap(), pattern == groups->group_pattern ? groups->ratio : -1);
              selected = snap::select_direction(cells, selected,
                  event.keycode == KEY_LEFT ? -1 : (event.keycode == KEY_RIGHT ? 1 : 0),
                  event.keycode == KEY_UP ? -1 : (event.keycode == KEY_DOWN ? 1 : 0));
              break;
          }
          case KEY_TAB: pattern = (pattern + 1) % 6; selected = 0; break;
          default:
            if (event.keycode >= KEY_1 && event.keycode <= KEY_6)
            { pattern = event.keycode - KEY_1; selected = 0; }
            else return;
        }
        auto area = output->workarea->get_workarea();
        auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern, groups->gap(), pattern == groups->group_pattern ? groups->ratio : -1);
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
        bindings.clear();
        grab.reset();
        gestures.reset();
        divider.reset();
        groups.reset();
    }
};
DECLARE_WAYFIRE_PLUGIN(wf::per_output_plugin_t<snap_output>);
