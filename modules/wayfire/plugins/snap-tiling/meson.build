project('snap-tiling', 'cpp', default_options: ['cpp_std=c++17', 'warning_level=2'])
wayfire = dependency('wayfire', version: '>=0.11.0')
drag = meson.get_compiler('cpp').find_library('wayfire-move-drag-interface')
shared_module('snap-tiling', 'snap-tiling.cpp', dependencies: [wayfire, drag],
  install: true, install_dir: get_option('libdir') / 'wayfire')
install_data('snap-tiling.xml', install_dir: get_option('datadir') / 'wayfire/metadata')
