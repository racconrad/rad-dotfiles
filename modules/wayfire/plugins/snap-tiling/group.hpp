#pragma once
#include "layout.hpp"
#include "selection.hpp"
#include <wayfire/core.hpp>
#include <wayfire/output.hpp>
#include <wayfire/seat.hpp>
#include <wayfire/signal-definitions.hpp>
#include <wayfire/toplevel-view.hpp>
#include <wayfire/workarea.hpp>
#include <wayfire/txn/transaction-manager.hpp>
#include <linux/input-event-codes.h>
#include <map>
#include <wayfire/option-wrapper.hpp>

namespace snap
{
class group_controller
{
    wf::output_t *output;
    wf::option_wrapper_t<int> gap_option{"snap-tiling/gap"};
    std::vector<std::weak_ptr<wf::toplevel_view_interface_t>> group;
  public:
    int gap() const
    {
        auto area = output->workarea->get_workarea();
        return std::clamp(int(gap_option), 0, int(std::max(0.0, std::min(area.width, area.height) / 8)));
    }
    double ratio = 0.5;
    unsigned group_pattern = 6;
    std::map<std::weak_ptr<wf::toplevel_view_interface_t>, wf::geometry_t,
        std::owner_less<std::weak_ptr<wf::toplevel_view_interface_t>>> saved;
    void restore(std::shared_ptr<wf::toplevel_view_interface_t> view)
    {
        auto found = saved.find(view);
        if (found == saved.end()) return;
        if (view->is_mapped() && view->get_output() == output)
        {
            view->toplevel()->pending().geometry = found->second;
            view->toplevel()->pending().tiled_edges = 0;
            wf::get_core().tx_manager->schedule_object(view->toplevel());
        }
        saved.erase(found);
    }
    wf::key_callback detach = [this] (const wf::keybinding_t&)
    {
        auto view = wf::toplevel_cast(wf::get_active_view_for_output(output));
        if (!view || saved.find(view->weak_from_this()) == saved.end()) return false;
        restore(view->shared_from_this());
        for (auto& weak : group) if (weak.lock().get() == view.get()) weak.reset();
        return true;
    };
    wf::key_callback focus = [this] (const wf::keybinding_t& key)
    {
        auto view = wf::toplevel_cast(wf::get_active_view_for_output(output));
        if (!view || saved.find(view->weak_from_this()) == saved.end()) return false;
        auto origin = view->get_geometry();
        auto code = key.get_key();
        std::shared_ptr<wf::toplevel_view_interface_t> nearest;
        double best = 1e30;
        for (auto weak : group)
        {
            auto candidate = weak.lock();
            if (!candidate || candidate.get() == view.get() || !candidate->is_mapped() || candidate->get_output() != output) continue;
            auto geometry = candidate->get_geometry();
            double dx = geometry.x + geometry.width / 2 - origin.x - origin.width / 2;
            double dy = geometry.y + geometry.height / 2 - origin.y - origin.height / 2;
            if ((code == KEY_LEFT && dx >= 0) || (code == KEY_RIGHT && dx <= 0) ||
                (code == KEY_UP && dy >= 0) || (code == KEY_DOWN && dy <= 0)) continue;
            auto distance = dx * dx + dy * dy;
            if (distance < best) { best = distance; nearest = candidate; }
        }
        if (nearest) wf::get_core().seat->focus_view(nearest.get());
        return bool(nearest);
    };
    bool divider_hit(wf::pointf_t point)
    {
        if (group.size() != 2) return false;
        auto first = group[0].lock(), second = group[1].lock();
        if (!first || !second || !first->is_mapped() || !second->is_mapped() ||
            first->get_output() != output || second->get_output() != output) return false;
        auto bounds = output->get_layout_geometry();
        point.x -= bounds.x; point.y -= bounds.y;
        auto area = output->workarea->get_workarea();
        auto geometry = first->get_geometry();
        if (group_pattern < 3)
            return point.y >= area.y && point.y < area.y + area.height &&
                std::abs(point.x - geometry.x - geometry.width - gap() / 2.0) <= 6;
        return point.x >= area.x && point.x < area.x + area.width &&
            std::abs(point.y - geometry.y - geometry.height - gap() / 2.0) <= 6;
    }
    void divider_move(wf::pointf_t point)
    {
        auto bounds = output->get_layout_geometry();
        auto area = output->workarea->get_workarea();
        double previous = ratio;
        ratio = group_pattern < 3 ? (point.x - bounds.x - area.x - gap() / 2.0) / (std::max(1.0, area.width - gap())) :
            (point.y - bounds.y - area.y - gap() / 2.0) / (std::max(1.0, area.height - gap()));
        ratio = std::clamp(ratio, 0.2, 0.8);
        if (!arrange_group()) ratio = previous;
    }
    wf::signal::connection_t<wf::view_disappeared_signal> unmapped = [this] (wf::view_disappeared_signal *event)
    {
        bool changed = false;
        for (auto& weak : group)
            if (auto view = weak.lock(); view && view.get() == event->view.get())
            {
                if (view->is_mapped())
                {
                    view->toplevel()->pending().tiled_edges = 0;
                    wf::get_core().tx_manager->schedule_object(view->toplevel());
                }
                saved.erase(view->weak_from_this());
                weak.reset(); changed = true;
            }
        if (!changed) return;
        std::vector<std::shared_ptr<wf::toplevel_view_interface_t>> remaining;
        for (auto weak : group)
            if (auto view = weak.lock(); view && view->is_mapped() && view->get_output() == output)
                remaining.push_back(view);
        if (remaining.size() != 1) return;
        auto view = remaining.front();
        view->toplevel()->pending().geometry = output->workarea->get_workarea();
        auto tx = wf::txn::transaction_t::create();
        tx->add_object(view->toplevel());
        wf::get_core().tx_manager->schedule_transaction(std::move(tx));
        group.clear();
        group_pattern = 6;
    };
    wf::key_callback resize = [this] (const wf::keybinding_t& key)
    {
        auto focused = wf::toplevel_cast(wf::get_active_view_for_output(output));
        bool member = false;
        for (auto weak : group) if (auto view = weak.lock()) member |= view.get() == focused.get();
        if (!member || group.size() != 2) return false;
        const auto code = key.get_key();
        const bool rows = group_pattern >= 3;
        if (rows != (code == KEY_UP || code == KEY_DOWN)) return false;
        const double old_ratio = ratio;
        ratio = std::clamp(ratio + ((code == KEY_LEFT || code == KEY_UP) ? -0.05 : 0.05), 0.2, 0.8);
        if (!arrange_group()) ratio = old_ratio;
        return true;
    };
    bool arrange_group()
    {
        auto area = output->workarea->get_workarea();
        auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, group_pattern, gap(), ratio);
        if (cells.size() != group.size()) return false;
        auto tx = wf::txn::transaction_t::create();
        for (unsigned i = 0; i < group.size(); ++i)
        {
            auto view = group[i].lock();
            if (!view || !view->is_mapped() || view->get_output() != output) continue;
            auto cell = cells[i];
            auto minimum = view->toplevel()->get_min_size();
            if (!fits(cell, minimum.width, minimum.height)) return false;
        }
        for (unsigned i = 0; i < group.size(); ++i)
        {
            auto view = group[i].lock();
            if (!view || !view->is_mapped() || view->get_output() != output) continue;
            auto cell = cells[i];
            view->toplevel()->pending().geometry = {double(cell.x), double(cell.y), double(cell.width), double(cell.height)};
            view->toplevel()->pending().tiled_edges = 15;
            tx->add_object(view->toplevel());
        }
        wf::get_core().tx_manager->schedule_transaction(std::move(tx));
        return true;
    }

    void reset()
    {
        for (auto weak : group) if (auto view = weak.lock()) restore(view);
        group.clear();
        group_pattern = 6;
    }
    void release_workspace()
    {
        for (auto weak : group)
            if (auto view = weak.lock(); view && view->is_mapped())
            {
                view->toplevel()->pending().tiled_edges = 0;
                wf::get_core().tx_manager->schedule_object(view->toplevel());
            }
        group.clear();
        saved.clear();
        group_pattern = 6;
    }
    wf::signal::connection_t<wf::workspace_changed_signal> workspace_changed =
        [this] (auto*) { release_workspace(); };
    wf::signal::connection_t<wf::workspace_set_changed_signal> workspace_set_changed =
        [this] (auto*) { release_workspace(); };
    wf::signal::connection_t<wf::workarea_changed_signal> workarea_changed =
        [this] (auto*) { if (!arrange_group()) reset(); };
    explicit group_controller(wf::output_t *output) : output(output)
    {
        output->connect(&unmapped);
        output->connect(&workspace_changed);
        output->connect(&workspace_set_changed);
        output->connect(&workarea_changed);
    }
    ~group_controller()
    {
        unmapped.disconnect();
        workspace_changed.disconnect();
        workspace_set_changed.disconnect();
        workarea_changed.disconnect();
        while (!saved.empty())
        {
            auto view = saved.begin()->first.lock();
            if (view) restore(view);
            else saved.erase(saved.begin());
        }
    }
    void place(std::shared_ptr<wf::toplevel_view_interface_t> view, unsigned pattern, unsigned selected)
    {
        auto area = output->workarea->get_workarea();
        auto cells = layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern);
        if (cells.empty()) return;
        const double next_ratio = group_pattern == pattern ? ratio :
            (pattern == 1 ? 1.0 / 3 : (pattern == 4 ? 0.7 : 0.5));
        cells = layout({int(area.x), int(area.y), int(area.width), int(area.height)}, pattern, gap(), next_ratio);
        auto proposed = group_pattern == pattern ? group : decltype(group)(cells.size());
        for (auto& weak : proposed) if (weak.lock() == view) weak.reset();
        proposed[selected % cells.size()] = view;
        for (unsigned i = 0; i < proposed.size(); ++i)
        {
            auto member = proposed[i].lock();
            if (!member) continue;
            if (!member->is_mapped() || member->get_output() != output) return;
            auto minimum = member->toplevel()->get_min_size();
            if (!fits(cells[i], minimum.width, minimum.height)) return;
        }
        if (group_pattern != pattern)
        {
            for (auto weak : group) if (auto member = weak.lock()) restore(member);
            group.clear();
            group.resize(cells.size());
            group_pattern = pattern;
            ratio = pattern == 1 ? 1.0 / 3 : (pattern == 4 ? 0.7 : 0.5);
        }
        for (auto& weak : group) if (weak.lock() == view) weak.reset();
        if (auto displaced = group[selected % cells.size()].lock(); displaced && displaced != view) restore(displaced);
        saved.emplace(view, view->get_geometry());
        group[selected % cells.size()] = view;
        arrange_group();
    }
};
}
