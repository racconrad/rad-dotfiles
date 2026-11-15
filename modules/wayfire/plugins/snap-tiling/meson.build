project('snap-tiling', 'cpp', default_options: ['cpp_std=c++17', 'warning_level=2'])
wayfire = dependency('wayfire', version: '>=0.11.0')
text = dependency('pangocairo')
shared_module('snap-tiling', 'snap-tiling.cpp', dependencies: [wayfire, text],
  install: true, install_dir: get_option('libdir') / 'wayfire')
install_data('snap-tiling.xml', install_dir: get_option('datadir') / 'wayfire/metadata')
