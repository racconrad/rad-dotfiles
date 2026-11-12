#pragma once

#include <wayfire/plugins/common/input-grab.hpp>
#include <wayfire/signal-definitions.hpp>
#include <linux/input-event-codes.h>
#include <functional>

namespace snap
{
class divider : public wf::pointer_interaction_t
{
    wf::output_t *output;
    std::unique_ptr<wf::input_grab_t> grab;
    wf::plugin_activation_data_t activation;
    std::function<bool(wf::pointf_t)> hit;
    std::function<void(wf::pointf_t)> move;
    bool active = false;
    wf::signal::connection_t<wf::input_event_signal<wlr_pointer_button_event>> button = [this] (auto *event)
    {
        if (event->event->button != BTN_LEFT) return;
        if (active)
        {
            event->mode = wf::input_event_processing_mode_t::IGNORE;
            if (event->event->state == WL_POINTER_BUTTON_STATE_RELEASED) stop();
            return;
        }
        if (event->event->state != WL_POINTER_BUTTON_STATE_PRESSED ||
            wf::get_core().seat->get_active_output() != output) return;
        if (!hit(wf::get_core().get_cursor_position())) return;
        if (!output->activate_plugin(&activation)) return;
        active = true;
        event->mode = wf::input_event_processing_mode_t::IGNORE;
        grab->grab_input(wf::scene::layer::OVERLAY);
        wf::get_core().set_cursor("crosshair");
    };
    void stop()
    {
        if (!active) return;
        active = false;
        if (grab->is_grabbed()) grab->ungrab_input();
        output->deactivate_plugin(&activation);
        wf::get_core().set_cursor("default");
    }
  public:
    divider(wf::output_t *output, std::function<bool(wf::pointf_t)> hit,
        std::function<void(wf::pointf_t)> move) : output(output), hit(hit), move(move)
    {
        activation.name = "snap-divider";
        activation.capabilities = wf::CAPABILITY_GRAB_INPUT;
        activation.cancel = [this] { stop(); };
        grab = std::make_unique<wf::input_grab_t>("snap-divider", output, nullptr, this);
        wf::get_core().connect(&button);
    }
    void handle_pointer_motion(wf::pointf_t, uint32_t) override
    {
        if (active) move(wf::get_core().get_cursor_position());
    }
    ~divider() override
    {
        button.disconnect();
        stop();
    }
};
}
