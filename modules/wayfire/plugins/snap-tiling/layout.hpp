#pragma once

#include <algorithm>
#include <vector>

namespace snap
{
struct box
{
    int x, y, width, height;
};

inline std::vector<box> layout(box area, unsigned pattern, int gap = 10, double ratio = -1)
{
    if (area.width <= 0 || area.height <= 0 || pattern > 5)
        return {};
    gap = std::clamp(gap, 0, std::max(0, std::min(area.width, area.height) / 8));
    const bool rows = pattern == 3 || pattern == 4;
    const int columns = pattern == 2 ? 3 : 2;
    if (pattern == 5)
    {
        auto halves = layout(area, 3, gap);
        std::vector<box> result;
        for (auto half : halves)
            for (auto cell : layout(half, 0, gap))
                result.push_back(cell);
        return result;
    }
    const int total = (rows ? area.height : area.width) - gap * (columns - 1);
    if (total < columns)
        return {};
    if (ratio < 0) ratio = pattern == 1 ? 1.0 / 3 : (pattern == 4 ? 0.7 : 0.5);
    ratio = std::clamp(ratio, 0.1, 0.9);
    std::vector<box> result;
    int offset = 0;
    for (int i = 0; i < columns; ++i)
    {
        int size = i == columns - 1 ? total - offset + gap * i :
            (columns == 3 ? total / columns : int(total * ratio));
        result.push_back(rows ? box{area.x, area.y + offset, area.width, size} :
            box{area.x + offset, area.y, size, area.height});
        offset += size + gap;
    }
    return result;
}
}
