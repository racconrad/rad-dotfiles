#pragma once

#include "layout.hpp"
#include <optional>
#include <utility>

namespace snap
{
struct selector_layout
{
    box panel;
    int columns, rows;

    explicit selector_layout(box area)
    {
        const int width = std::max(1, std::min(660, area.width - 16));
        columns = width >= 600 ? 3 : (width >= 280 ? 2 : 1);
        rows = (6 + columns - 1) / columns;
        const int height = std::max(1, std::min(80 + rows * 82, area.height - 16));
        panel = {area.x + (area.width - width) / 2, area.y + std::min(24, std::max(0, area.height - height)), width, height};
    }

    box card(unsigned pattern) const
    {
        const int width = std::max(1, (panel.width - 32 - (columns - 1) * 10) / columns);
        const int height = std::max(1, (panel.height - 80 - (rows - 1) * 10) / rows);
        return {panel.x + 16 + int(pattern % columns) * (width + 10),
            panel.y + 44 + int(pattern / columns) * (height + 10), width, height};
    }

    bool usable() const { return panel.width >= 280 && card(0).height >= 44; }

    std::vector<box> slots(unsigned pattern) const
    {
        if (!usable()) return {};
        auto bounds = card(pattern);
        return layout({bounds.x + 8, bounds.y + 26, std::max(1, bounds.width - 16),
            std::max(1, bounds.height - 34)}, pattern, 3);
    }

    bool contains(double x, double y) const
    {
        return x >= panel.x && y >= panel.y && x < panel.x + panel.width && y < panel.y + panel.height;
    }

    std::optional<std::pair<unsigned, unsigned>> hit(double x, double y) const
    {
        for (unsigned pattern = 0; pattern < 6; ++pattern)
        {
            auto cells = slots(pattern);
            for (unsigned slot = 0; slot < cells.size(); ++slot)
            {
                const auto& cell = cells[slot];
                if (x >= cell.x && y >= cell.y && x < cell.x + cell.width && y < cell.y + cell.height)
                    return std::pair{pattern, slot};
            }
        }
        return std::nullopt;
    }
};
}
