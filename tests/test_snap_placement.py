"""Compile the real native placement policy without a compositor."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SnapPlacementTests(unittest.TestCase):
    def test_native_constraints_and_margin_policy(self):
        source = r'''
#include <policy.hpp>
#include <cassert>
int main() {
    assert(snap::floating_state_error(false, 0).empty());
    assert(!snap::floating_state_error(false, 15).empty());
    assert(!snap::floating_state_error(false, 1).empty());
    assert(!snap::floating_state_error(true, 0).empty());
    snap::client_limits restore_limits{200, 150, 0, 0};
    assert(snap::can_restore({20,30,500,320}, {0,0,1280,800}, restore_limits));
    assert(!snap::can_restore({20,30,500,320}, {0,0,480,300}, restore_limits));
    assert(!snap::can_restore({20,30,100,100}, {0,0,1280,800}, restore_limits));
    snap::client_limits limits{300, 200, 0, 0, 8, 8, 30, 8};
    assert(snap::placement_error({0,0,316,238}, limits).empty());
    assert(!snap::placement_error({0,0,315,238}, limits).empty());
    assert(!snap::placement_error({0,0,316,237}, limits).empty());
    assert(snap::placement_error({0,0,500,400}, limits).empty());
    limits.max_width=500; limits.max_height=400;
    assert(snap::placement_error({0,0,516,438}, limits).empty());
    assert(!snap::placement_error({0,0,517,438}, limits).empty());
    assert(!snap::placement_error({0,0,516,439}, limits).empty());
    assert(!snap::placement_error({0,0,0,100}, limits).empty());
    assert(!snap::placement_error({0,0,100,-1}, limits).empty());
    snap::client_limits unconstrained{};
    assert(snap::placement_error({0,0,100,100}, unconstrained).empty());
    assert(!snap::placement_error({0,0,0,0}, unconstrained).empty());
    limits.min_width=500; limits.min_height=400;
    assert(snap::placement_error({0,0,516,438}, limits).empty());
    assert(!snap::placement_error({0,0,600,500}, limits).empty());
    assert(!snap::placement_error({0,0,300,200}, limits).empty());
    limits.left=0.5; limits.right=0.5; limits.top=0.5; limits.bottom=0.5;
    assert(snap::placement_error({0,0,501,401}, limits).empty());
    assert(!snap::placement_error({0,0,500,401}, limits).empty());
}
'''
        include = ROOT / 'modules/wayfire/plugins/snap-tiling'
        with tempfile.TemporaryDirectory(prefix='snap-policy-') as folder:
            folder = Path(folder)
            path = folder / 'test.cpp'
            path.write_text(source)
            binary = folder / 'test'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(include), str(path), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_controller_compiles_against_installed_wayfire(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', 'wayfire'], text=True))
        source = '#include <placement.hpp>\n'
        include = ROOT / 'modules/wayfire/plugins/snap-tiling'
        subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        *flags, '-I', str(include), '-x', 'c++', '-fsyntax-only', '-'],
                       input=source, text=True, check=True)
