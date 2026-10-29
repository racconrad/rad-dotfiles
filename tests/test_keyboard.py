"""Headless checks for directional selection and native module revision tracking."""
import importlib.util
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
import os

LIB=Path(__file__).resolve().parents[1]/'modules/desktop/files/.local/lib/raccon_menu'
class KeyboardTests(unittest.TestCase):
    def test_directional_geometry_preserves_column_and_rejects_reverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'navigation.c';binary=Path(tmp)/'navigation'
            source.write_text('#include "'+str(LIB/'navigation.h')+'"\n'+r'''
int main(void) {
    g_assert(nav_score(100,0,GDK_KEY_Right)<nav_score(100,160,GDK_KEY_Right));
    g_assert(nav_score(0,160,GDK_KEY_Down)<nav_score(220,160,GDK_KEY_Down));
    g_assert(nav_score(0,-160,GDK_KEY_Up)<nav_score(220,-160,GDK_KEY_Up));
    g_assert(nav_score(-220,0,GDK_KEY_Left)<nav_score(-220,160,GDK_KEY_Left));
    g_assert(nav_score(-20,0,GDK_KEY_Right)==G_MAXDOUBLE);
    g_assert(nav_score(0,-20,GDK_KEY_Down)==G_MAXDOUBLE);
    return 0;
}
''')
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0'],text=True))
            subprocess.run(['cc',str(source),'-o',str(binary),*flags],check=True)
            subprocess.run([str(binary)],check=True)

    def test_shared_header_invalidates_resident_module(self):
        spec=importlib.util.spec_from_file_location('transport',LIB/'transport.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.c';source.touch()
            before=module.source_revision(source)
            header=source.with_name('navigation.h');header.touch()
            os.utime(header,ns=(int(before)+1000,int(before)+1000))
            self.assertEqual(module.source_revision(source),str(int(before)+1000))

if __name__=='__main__':unittest.main()
