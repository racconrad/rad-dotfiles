#pragma once

#include <wayfire/plugin.hpp>
#include <wayfire/core.hpp>
#include <wayfire/output.hpp>
#include <wayfire/seat.hpp>
#include <wayfire/signal-definitions.hpp>
#include <wayfire/workspace-set.hpp>
#include <wayfire/plugins/common/shared-core-data.hpp>
#include <wayfire/plugins/ipc/ipc-method-repository.hpp>

namespace snap
{
class gestures
{
    wf::output_t *output;
    bool swiping = false, pinching = false;
    double dx = 0, dy = 0, scale = 1;
    wf::shared_data::ref_ptr_t<wf::ipc::method_repository_t> methods;
    bool allowed() const
    {
        return wf::get_core().seat->get_active_output() == output &&
            output->can_activate_plugin(wf::CAPABILITY_MANAGE_COMPOSITOR);
    }
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_swipe_begin_event>> swipe_begin =
        [this] (auto *event)
    {
        swiping = event->event->fingers == 4 && allowed();
        dx = dy = 0;
    };
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_swipe_update_event>> swipe_update =
        [this] (auto *event)
    {
        if (swiping) { dx += event->event->dx; dy += event->event->dy; }
    };
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_swipe_end_event>> swipe_end =
        [this] (auto *event)
    {
        const bool execute = swiping && !event->event->cancelled && allowed();
        swiping = false;
        if (!execute) return;
        if (std::abs(dx) > 80 && std::abs(dx) > std::abs(dy))
        {
            auto workspace = output->wset()->get_current_workspace();
            workspace.x += dx < 0 ? 1 : -1;
            if (output->wset()->is_workspace_valid(workspace)) output->wset()->request_workspace(workspace);
        } else if (dy < -80 && std::abs(dy) > std::abs(dx))
        {
            methods->call_method("scale/toggle", wf::json_t{});
        }
    };
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_pinch_begin_event>> pinch_begin =
        [this] (auto *event)
    {
        pinching = event->event->fingers == 4 && allowed();
        scale = 1;
    };
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_pinch_update_event>> pinch_update =
        [this] (auto *event) { if (pinching) scale = event->event->scale; };
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_pinch_end_event>> pinch_end =
        [this] (auto *event)
    {
        const bool execute = pinching && !event->event->cancelled && allowed();
        pinching = false;
        if (!execute) return;
        if (scale < 0.75) wf::get_core().run("desktop-menu");
        else if (scale > 1.25) methods->call_method("wm-actions/toggle_showdesktop", wf::json_t{});
    };

  public:
    explicit gestures(wf::output_t *output) : output(output)
    {
        auto& core = wf::get_core();
        core.connect(&swipe_begin);
        core.connect(&swipe_update);
        core.connect(&swipe_end);
        core.connect(&pinch_begin);
        core.connect(&pinch_update);
        core.connect(&pinch_end);
    }
};
}
