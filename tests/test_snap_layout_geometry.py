import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_native_layout_geometry():
    source = r'''
#include <layout.hpp>
#include <selection.hpp>
#include <cassert>
int main() {
    using snap::layout;
    auto grid = layout({0,0,1000,800},5);
    assert(snap::select_direction(grid,0,1,0)==1);
    assert(snap::select_direction(grid,0,0,1)==2);
    assert(snap::select_direction(grid,0,-1,0)==0);
    assert(snap::select_at(grid,800,600)==3);
    auto row_slots=layout({0,0,1000,800},3);
    assert(snap::select_at(row_slots,500,700)==1);
    assert(!snap::fits({0,0,190,500},200,100));
    assert(snap::fits({0,0,400,500},200,100));
    auto pair = layout({10,20,1000,800},0);
    assert(pair.size()==2);
    assert(pair[0].width==495 && pair[1].width==495);
    assert(pair[1].x==515);
    auto rows = layout({10,20,1000,800},3);
    assert(rows[0].height==395 && rows[1].y==425);
    for (unsigned pattern=0;pattern<6;++pattern) {
        auto cells=layout({10,20,1001,801},pattern);
        assert(!cells.empty());
        for(auto cell:cells) {
            assert(cell.width>0 && cell.height>0);
            assert(cell.x>=10 && cell.y>=20);
            assert(cell.x+cell.width<=1011 && cell.y+cell.height<=821);
        }
    }
    auto thirds = layout({0,0,1000,800},1);
    assert(thirds[0].width==330 && thirds[1].width==660);
    auto adjusted = layout({0,0,1000,800},1,10,0.6);
    assert(adjusted[0].width==594 && adjusted[1].width==396);
    auto extreme = layout({0,0,1000,800},0,10,2);
    assert(extreme[0].width==891 && extreme[1].width==99);
    for(int width=20;width<1200;width+=17)
      for(int height=20;height<900;height+=19)
        for(unsigned pattern=0;pattern<6;++pattern) {
          auto cells=layout({-40,-80,width,height},pattern,10000);
          for(auto cell:cells) {
            assert(cell.x>=-40 && cell.y>=-80);
            assert(cell.x+cell.width<=width-40);
            assert(cell.y+cell.height<=height-80);
            assert(cell.width>0 && cell.height>0);
          }
        }
    assert(layout({0,0,0,10},0).empty());
    assert(layout({0,0,100,100},6).empty());
}
'''
    with tempfile.TemporaryDirectory() as directory:
        source_path = pathlib.Path(directory) / 'test.cpp'
        executable = pathlib.Path(directory) / 'test'
        source_path.write_text(source)
        subprocess.run(['c++', '-std=c++17', '-Wall', '-Werror', '-I', str(ROOT / 'modules/wayfire/plugins/snap-tiling'), str(source_path), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


class SnapLayoutTests(unittest.TestCase):
    def test_native_layout_geometry(self):
        run_native_layout_geometry()


if __name__ == '__main__':
    unittest.main()
