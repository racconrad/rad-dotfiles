import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SnapSelectorTests(unittest.TestCase):
    def test_native_selector_layout_and_hit_testing(self):
        source = r'''
#include <hud-model.hpp>
#include <cassert>
int main() {
    auto ui = snap::selector_layout({0,0,1280,720});
    assert(ui.panel.width <= 680 && ui.panel.height < 300);
    assert(ui.panel.y >= 0 && ui.panel.x > 0);
    for (unsigned pattern = 0; pattern < 6; ++pattern) {
        auto mini = ui.slots(pattern);
        assert(mini.size() == snap::layout({0,0,800,600},pattern).size());
        for (unsigned slot = 0; slot < mini.size(); ++slot) {
            auto cell = mini[slot];
            auto hit = ui.hit(cell.x + cell.width / 2., cell.y + cell.height / 2.);
            assert(hit && hit->first == pattern && hit->second == slot);
            assert(cell.x >= ui.panel.x && cell.y >= ui.panel.y);
            assert(cell.x + cell.width <= ui.panel.x + ui.panel.width);
            assert(cell.y + cell.height <= ui.panel.y + ui.panel.height);
        }
    }
    auto tiny = snap::selector_layout({0,0,240,160});
    assert(!tiny.usable());
    assert(tiny.slots(0).empty());
    assert(!tiny.hit(100,100));
    assert(snap::selector_layout({0,0,320,360}).usable());
    assert(!ui.hit(0,0));
    assert(!ui.hit(ui.panel.x + 12, ui.panel.y + 12));
    for (int width : {220,320,640,1280}) {
        auto small = snap::selector_layout({50,70,width,400});
        assert(small.panel.x >= 50 && small.panel.y >= 70);
        assert(small.panel.x + small.panel.width <= 50 + width);
        assert(small.panel.y + small.panel.height <= 470);
    }
}
'''
        with tempfile.TemporaryDirectory() as folder:
            file = pathlib.Path(folder) / 'selector.cpp'
            executable = pathlib.Path(folder) / 'selector'
            file.write_text(source)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Werror', '-I', str(ROOT / 'modules/wayfire/plugins/snap-tiling'), str(file), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
