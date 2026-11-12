#pragma once
#include "layout.hpp"
#include <limits>

namespace snap
{
inline bool fits(box cell, int width, int height)
{
    return cell.width >= std::max(200, width) && cell.height >= std::max(200, height);
}

inline unsigned select_direction(const std::vector<box>& cells, unsigned current, int dx, int dy)
{
    if (cells.empty()) return 0;
    current %= cells.size();
    auto origin = cells[current];
    double best = std::numeric_limits<double>::max();
    unsigned result = current;
    for (unsigned i = 0; i < cells.size(); ++i)
    {
        double x = cells[i].x + cells[i].width / 2.0 - origin.x - origin.width / 2.0;
        double y = cells[i].y + cells[i].height / 2.0 - origin.y - origin.height / 2.0;
        if ((dx && x * dx <= 0) || (dy && y * dy <= 0)) continue;
        double distance = x * x + y * y;
        if (distance < best) { best = distance; result = i; }
    }
    return result;
}

inline unsigned select_at(const std::vector<box>& cells, double x, double y)
{
    unsigned result = 0;
    double best = std::numeric_limits<double>::max();
    for (unsigned i = 0; i < cells.size(); ++i)
    {
        double dx = std::max({double(cells[i].x) - x, 0.0, x - cells[i].x - cells[i].width});
        double dy = std::max({double(cells[i].y) - y, 0.0, y - cells[i].y - cells[i].height});
        double distance = dx * dx + dy * dy;
        if (distance < best) { best = distance; result = i; }
    }
    return result;
}
}
