#pragma once
#include "policy.hpp"
#include <wayfire/core.hpp>
#include <wayfire/output.hpp>
#include <wayfire/signal-definitions.hpp>
#include <wayfire/toplevel-view.hpp>
#include <wayfire/workarea.hpp>
#include <wayfire/txn/transaction-manager.hpp>
#include <wayfire/workspace-set.hpp>
#include <map>
#include <memory>

namespace snap
{
class placement_controller
{
    using view_ptr = std::shared_ptr<wf::toplevel_view_interface_t>;
    using weak_view = std::weak_ptr<wf::toplevel_view_interface_t>;
    struct saved_state
    {
        wf::geometry_t geometry;
        uint32_t tiled_edges, gravity;
        std::weak_ptr<wf::workspace_set_t> workspace_set;
        wf::point_t workspace;
    };
    wf::output_t *output;
    std::map<weak_view, saved_state, std::owner_less<weak_view>> saved;
    wf::signal::connection_t<wf::view_disappeared_signal> disappeared = [this] (auto *event)
    {
        for (auto it = saved.begin(); it != saved.end();)
        {
            auto view = it->first.lock();
            if (!view || view.get() == event->view.get()) it = saved.erase(it);
            else ++it;
        }
    };

    std::string target_error(const view_ptr& view) const
    {
        if (!view || !view->is_mapped() || !view->toplevel()->pending().mapped || view->minimized)
            return "Choose an open window first";
        if (view->get_output() != output || view->get_wset() != output->wset())
            return "This window is on another desktop";
        if (view->parent)
            return "Dialogs cannot be snapped";
        if (auto error = floating_state_error(view->pending_fullscreen(), view->pending_tiled_edges());
            !error.empty()) return error;
        const auto allowed = view->get_allowed_actions();
        if (!(allowed & wf::VIEW_ALLOW_MOVE) || !(allowed & wf::VIEW_ALLOW_RESIZE))
            return "This window cannot be moved or resized";
        if (!output->wset()->view_visible_on(view.get(), output->wset()->get_current_workspace()))
            return "This window is on another workspace";
        return {};
    }

    client_limits limits(const view_ptr& view) const
    {
        const auto minimum = view->toplevel()->get_min_size();
        const auto maximum = view->toplevel()->get_max_size();
        // Pending decoration margins are not finalized until transaction commit.
        const auto margins = view->toplevel()->current().margins;
        return {double(minimum.width), double(minimum.height), double(maximum.width),
            double(maximum.height), margins.left, margins.right, margins.top, margins.bottom};
    }

  public:
    explicit placement_controller(wf::output_t *output) : output(output)
    {
        output->connect(&disappeared);
    }

    ~placement_controller()
    {
        disappeared.disconnect();
    }

    std::string can_place(const view_ptr& view, const box& cell) const
    {
        if (auto error = target_error(view); !error.empty()) return error;
        return placement_error(cell, limits(view));
    }

    std::string place(const view_ptr& view, const box& cell)
    {
        if (auto error = can_place(view, cell); !error.empty()) return error;
        const auto state = view->toplevel()->pending();
        const auto current_set = view->get_wset();
        const auto current_workspace = output->wset()->get_current_workspace();
        auto previous = saved.find(view);
        if (previous == saved.end() || previous->second.workspace_set.lock() != current_set ||
            previous->second.workspace.x != current_workspace.x ||
            previous->second.workspace.y != current_workspace.y)
            saved.insert_or_assign(view, saved_state{state.geometry, state.tiled_edges, state.gravity,
                current_set, current_workspace});
        auto& pending = view->toplevel()->pending();
        pending.geometry = {double(cell.x), double(cell.y), double(cell.width), double(cell.height)};
        // Tiling every edge advertises maximization to clients; a zone is not maximization.
        pending.tiled_edges = 0;
        pending.gravity = WLR_EDGE_TOP | WLR_EDGE_LEFT;
        auto transaction = wf::txn::transaction_t::create();
        transaction->add_object(view->toplevel());
        wf::get_core().tx_manager->schedule_transaction(std::move(transaction));
        return {};
    }

    bool restore(const view_ptr& view)
    {
        if (!target_error(view).empty()) return false;
        auto found = saved.find(view);
        if (found == saved.end()) return false;
        const auto& state = found->second;
        const auto workspace = output->wset()->get_current_workspace();
        if (state.workspace_set.lock() != view->get_wset() ||
            state.workspace.x != workspace.x || state.workspace.y != workspace.y)
            return false;
        const auto geometry = state.geometry;
        const auto area = output->workarea->get_workarea();
        const box saved_box{int(std::lround(geometry.x)), int(std::lround(geometry.y)),
            int(std::lround(geometry.width)), int(std::lround(geometry.height))};
        const box current_area{int(area.x), int(area.y), int(area.width), int(area.height)};
        if (!can_restore(saved_box, current_area, limits(view))) return false;
        auto& pending = view->toplevel()->pending();
        pending.geometry = state.geometry;
        pending.tiled_edges = state.tiled_edges;
        pending.gravity = state.gravity;
        auto transaction = wf::txn::transaction_t::create();
        transaction->add_object(view->toplevel());
        wf::get_core().tx_manager->schedule_transaction(std::move(transaction));
        saved.erase(found);
        return true;
    }
};
}
