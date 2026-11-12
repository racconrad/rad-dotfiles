#pragma once
#include "layout.hpp"
#include <wayfire/core.hpp>
#include <wayfire/output.hpp>
#include <wayfire/seat.hpp>
#include <wayfire/signal-definitions.hpp>
#include <wayfire/toplevel-view.hpp>
#include <wayfire/workarea.hpp>
#include <wayfire/txn/transaction-manager.hpp>
#include <linux/input-event-codes.h>
#include <map>

namespace snap
{
class group_controller
{
    wf::output_t *output;
    std::vector<std::weak_ptr<wf::toplevel_view_interface_t>> group;
  public:
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
                std::abs(point.x - geometry.x - geometry.width - 5) <= 6;
        return point.x >= area.x && point.x < area.x + area.width &&
            std::abs(point.y - geometry.y - geometry.height - 5) <= 6;
    }
    void divider_move(wf::pointf_t point)
    {
        auto bounds = output->get_layout_geometry();
        auto area = output->workarea->get_workarea();
        double previous = ratio;
        ratio = group_pattern < 3 ? (point.x - bounds.x - area.x - 5) / (area.width - 10) :
            (point.y - bounds.y - area.y - 5) / (area.height - 10);
        ratio = std::clamp(ratio, 0.2, 0.8);
        if (!arrange_group()) ratio = previous;
    }
    wf::signal::connection_t<wf::view_unmapped_signal> unmapped = [this] (wf::view_unmapped_signal *event)
    {
        bool changed = false;
        for (auto& weak : group)
            if (auto view = weak.lock(); view && view.get() == event->view.get())
            { weak.reset(); changed = true; }
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
        auto cells = snap::layout({int(area.x), int(area.y), int(area.width), int(area.height)}, group_pattern, 10, ratio);
        if (cells.size() != group.size()) return false;
        auto tx = wf::txn::transaction_t::create();
        for (unsigned i = 0; i < group.size(); ++i)
        {
            auto view = group[i].lock();
            if (!view || !view->is_mapped() || view->get_output() != output) continue;
            auto cell = cells[i];
            auto minimum = view->toplevel()->get_min_size();
            if (cell.width < std::max(200, minimum.width) || cell.height < std::max(200, minimum.height)) return false;
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

    explicit group_controller(wf::output_t *output) : output(output) { output->connect(&unmapped); }
    ~group_controller()
    {
        unmapped.disconnect();
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
