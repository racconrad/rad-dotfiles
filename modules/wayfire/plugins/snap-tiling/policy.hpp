#pragma once
#include "layout.hpp"
#include <cmath>
#include <string>

namespace snap
{
inline std::string floating_state_error(bool fullscreen, unsigned tiled_edges)
{
    if (fullscreen) return "Leave fullscreen before snapping";
    if (tiled_edges) return "Restore the window to floating mode first";
    return {};
}

struct client_limits
{
    double min_width = 0, min_height = 0, max_width = 0, max_height = 0;
    double left = 0, right = 0, top = 0, bottom = 0;
};

inline std::string placement_error(const box& cell, const client_limits& limits)
{
    const double width = cell.width - limits.left - limits.right;
    const double height = cell.height - limits.top - limits.bottom;
    if (!std::isfinite(width) || !std::isfinite(height) || width < 1 || height < 1)
        return "This zone has no room for the window";
    if (width < limits.min_width)
        return "Window minimum width exceeds this zone";
    if (height < limits.min_height)
        return "Window minimum height exceeds this zone";
    if (limits.max_width > 0 && width > limits.max_width)
        return "Window maximum width is smaller than this zone";
    if (limits.max_height > 0 && height > limits.max_height)
        return "Window maximum height is smaller than this zone";
    return {};
}

inline bool can_restore(const box& geometry, const box& workarea, const client_limits& limits)
{
    if (geometry.width <= 0 || geometry.height <= 0 || geometry.x < workarea.x ||
        geometry.y < workarea.y || geometry.x + geometry.width > workarea.x + workarea.width ||
        geometry.y + geometry.height > workarea.y + workarea.height)
        return false;
    return placement_error(geometry, limits).empty();
}
}
