# Estilos del escritorio

Abre **Estilo del escritorio** desde las aplicaciones, o ejecuta `desktop-style`.
Selecciona una vista previa y pulsa **Aplicar estilo**. La selección permanece
entre sesiones y se reaplica cuando `wallpaper-theme` actualiza el wallpaper.
**Restaurar original** recupera las opciones anteriores de widgets, barra y
decoraciones, con la paleta del wallpaper vigente.

| Perfil | Apariencia |
| --- | --- |
| Default | Superficies opacas y redondeadas; unifica Moderno, GNOME y Windows |
| Transparent | Superficies translúcidas; antes Glass |
| Classic | Monoespaciada y bordes rectos; antes Terminal |
| Mono | Fondo del color dominante de la imagen y texto de contraste; dos colores opacos |
| Retro | Paleta de 16 colores y fuente pixel Silkscreen |
| Night | Azul noche, texto marfil y coral/cian; antes ASCII Bloom |

Comandos: `desktop-style apply default|transparent|classic|mono|retro|night`,
`desktop-style reset`, `desktop-style status`, `desktop-style list`.

Los identificadores anteriores siguen funcionando. `modern`, `gnome` y `windows`
aplican Default; las selecciones guardadas y sus marcos personalizados se migran.
Los marcos Rounded y Compact permanecen disponibles como formas independientes.

El selector conserva una sola vista previa visible de 440 × 280 en PNG; las otras
no se decodifican al abrir. Una caché compartida evita renderizar otra vez el
catálogo al cambiar de operación. Las actualizaciones se envían por FileEvents,
sin un segundo cliente Eww por interacción. El selector sigue siendo residente.

Barra y marcos se abren en un panel adjunto, como los desplegables de Raccon Menu.
Solo se muestra uno a la vez: pulsa de nuevo su icono o Esc para cerrarlo; otro
Esc cierra el selector. El panel se desliza durante 200 ms (140 ms en modo
reducido) y respeta la opción GTK de desactivar animaciones. En pantallas de
menos de 1080 px de ancho se despliega debajo para caber sin ensanchar la ventana.
Los marcos se crean al abrirlos por primera vez y conservan su contenido durante
la animación de cierre.

**Marco de widgets**: en el selector elige el marco que adoptan los widgets con
«Heredar escritorio» (Auto = el del estilo). También `desktop-style frame auto|none|monochrome|terminal|retro|future|glass|modern|gnome|windows|ascii`;
se guarda en `~/.local/state/desktop-style/widget-frame.json` y sobrevive al cambiar de estilo.

Atajo: **Super + Alt + T** abre o cierra el selector.

## Night

`desktop-style apply night` aplica la paleta curada azul noche/marfil/coral/cian
a la barra, menú, paneles, notificaciones, terminal, decoraciones y
widgets. Conserva esa identidad al cambiar el wallpaper; los demás perfiles
siguen usando la paleta original de la imagen. No usa parpadeos ni efectos
continuos. Los iconos de aplicaciones y sus imágenes conservan su contenido.

El selector ofrece un botón de wallpaper al seleccionar Night. También
`desktop-style background ascii`, que pasa por `wallpaper-set` y su protección
contra asignar otra vez la misma imagen. Los dots no incluyen fondos: coloca
tu propia imagen en `~/.local/share/wallpapers/raccon/ascii-bloom.png`.
Elegir el tema y elegir su fondo son acciones independientes.

tinyWidgets incluye el skin `ascii` y el marco `ASCII`: títulos `[ Widget ]`,
controles `[-] [:] [x]` y estado textual. En **Marcos por widget…** o
`widgetctl editor frames` puedes seleccionar varios y elegir **Seguir el tema**.
Las reglas **Sin marco** y **Estilo fijo** siguen teniendo prioridad; no se
reescriben instancias ni perfiles al cambiar de tema.

## Integración

La fuente visual común está en `desktop_style/appearance.py`. Cada perfil resuelve
fuente, radios, bordes, espaciado, transparencia, posición y colores una sola vez;
`current/tokens.json` registra ese contrato y los adaptadores producen los estilos
de cada superficie. También cubre los paneles de sonido, red y calendario, el
selector, las notificaciones y el OSD, incluidos los controles nativos.

La paleta original se conserva en
`~/.config/matugen/out/desktop-style-source.json`. Al aplicar un estilo se verifica
la identidad del wallpaper y se actualiza mediante Matugen si cambió; los colores
ya transformados de Waybar nunca se usan para recuperar la paleta original.
`source-colors.json` es su plantilla, no un respaldo de la selección activa.
Monocromo extrae el color dominante de la imagen con Pillow y conserva otro tono
con contraste de al menos 4.5:1. Si la imagen tiene poco contraste, ajusta ese tono
para texto legible; evita el azul de respaldo de Matugen en wallpapers grises.

- Reutiliza las plantillas de `~/.config/matugen/config.toml` para GTK, Qt,
  terminal, notificaciones, lanzadores, bloqueo y aplicaciones configuradas.
- Los menús toman colores, tipografía y geometría de `current/tokens.json`.
  Si no hay un perfil activo, usan la paleta de Waybar/Matugen como respaldo.
  Wallpaper, sesión y música mantienen sus importaciones dentro de su propia
  carpeta de Eww para detectar los cambios en vivo. Su listener de apariencia
  no depende de que Raccon Menu esté abierto; los perfiles estrictos también
  desactivan las transiciones correspondientes. Esto funciona aunque Matugen
  no exporte paletas para Waybar/Eww.
- Waybar y Rofi importan archivos de `current/`. Raccon Menu importa su archivo
  propio `_desktop-style.scss`, para que Eww detecte las actualizaciones. El menú conserva
  su estructura y lógica. Su paleta y los adaptadores se publican juntos. Waybar
  recibe una escritura terminada en su CSS principal, conservando el archivo
  vigilado; cambiar solo la fecha no recarga su estilo.
- Los widgets reciben la paleta y estilos por su puente nativo y API `widgetctl`.
  Los estilos globales se cargan después de los módulos y skins locales; un
  runtime anterior recibe reglas compatibles con mayor especificidad.
  No se habilitan widgets desactivados por el usuario o por el modo energético.
- El selector guarda su estado en `~/.local/state/desktop-style/ui.json` y lo
  escucha con `deflisten`. Antes de recargar, el estado inicial de Eww se
  actualiza en la misma transacción para que no aparezca brevemente Moderno
  dentro del estilo que se está aplicando.
- GNOME y Terminal sitúan también el menú y los paneles bajo su barra superior.
  Las reglas globales de GTK solo definen colores; la geometría se aplica en cada
  proceso para evitar que GTK conserve radios de un perfil anterior.
- El modo Working sigue evitando bloqueo y suspensión por inactividad mediante
  `idle-lock` e `idle-suspend`. La apariencia no modifica ese modo.

Los límites de 2/16 colores se aplican a la paleta del tema. Fotos, wallpapers,
iconos multicolor y contenido de aplicaciones conservan sus colores; el
suavizado de texto y los efectos del compositor pueden producir tonos intermedios.
Las aplicaciones con temas propios requieren su integración; algunas GTK/Qt
solo recargan la apariencia al volver a abrirse. GNOME y Windows son referencias
visuales sobre Wayfire, no cambios de entorno. Cambiar de estilo no modifica SDDM
automáticamente. El botón **Apply to SDDM** copia manualmente el estilo activo a
la pantalla de acceso mediante autenticación de polkit; primero aplica el tema
seleccionado al escritorio. El resultado se verá en el próximo inicio de sesión,
sin reiniciar la sesión actual. También puedes ejecutar `desktop-style sddm`.

## Archivos y recuperación

El motor está en `~/.local/lib/desktop_style/main.py`. Los respaldos del primer
uso se guardan en `~/.local/state/desktop-style/{original,settings,geometry}.json`.
Solo se restauran archivos generados y propiedades visuales gestionadas; nunca
se reemplaza por completo la configuración del menú o de Wayfire.

La fuente Silkscreen está en `~/.local/share/fonts/Silkscreen/`, con licencia OFL.
Las miniaturas son diagramas SVG del escritorio; Retro usa `rsvg-convert` para
evitar la caché de fuentes de procesos GTK que ya estaban abiertos.

Requisitos: Python 3.11+, Pillow, Eww, Matugen, Waybar, Rofi, librsvg,
las plantillas existentes y las fuentes indicadas por cada perfil.

Pruebas sin modificar el escritorio:
`python3 -m unittest discover -s tests -p test_desktop_styles.py` desde Raccon Dots.

## Cambio visual coordinado

Al aplicar un perfil, Waybar, selector, menú y widgets se desvanecen brevemente;
la nueva apariencia se publica mientras están ocultos y luego reaparecen.
Las aplicaciones mantienen su opacidad y siguen funcionando. El trabajador
`desktop_style/transition.py` restaura la visibilidad incluso si termina el
proceso que aplica el estilo. Sin Wayfire/alpha se aplica sin animación.
Para omitirla: `DESKTOP_STYLE_NO_TRANSITION=1 desktop-style apply monochrome`.

Los indicadores de volumen y brillo son compactos y transparentes. Monocromo
usa marcos rectos y separadores de terminal, con dos colores del wallpaper.

## Movimiento y teclado

El selector comparte la navegación espacial de Raccon Menu: flechas y Tab recorren
los controles; Enter/Espacio activan el control enfocado. Ctrl+1–8 elige una vista
previa, Ctrl+Enter aplica el estilo y Esc/Ctrl+W cierra con un fundido breve.
Seleccionar una vista previa nunca aplica el tema. El estilo en uso queda marcado.

Cabecera, lista, vista previa y pie aparecen de forma escalonada; las miniaturas
cambian con un fundido sin alterar el tamaño. Los botones responden al hover y
a la pulsación. El movimiento se acorta en los modos de energía reducida;
Monocromo, Terminal, Retro, ASCII Bloom y la preferencia GTK sin animaciones conservan cambios
inmediatos. El adaptador GTK se compila y renueva solo en la instancia del selector.

## Apertura residente y controles compactos

`desktop-style prewarm` prepara la ventana invisible al iniciar Wayfire. El selector
conserva su árbol GTK al cerrar; abrir, alternar y cerrar usan el FIFO nativo en
`$XDG_RUNTIME_DIR/desktop-style/control`, sin invocar clientes Eww ni reconstruir
miniaturas. La revisión del adaptador invalida el transporte cuando cambia su
fuente o `navigation.h`. La primera preparación publica el estado después de
arrancar el daemon y realiza un ciclo invisible de mostrar/ocultar para absorber
la primera reaparición lenta de GTK. Una recarga conserva si el selector estaba
visible u oculto. Solo se administra su propia instancia Eww.

La interfaz usa inglés, iconos de acciones con tooltips y nombres de perfiles.
El botón de ventanas junto al título de la miniatura despliega los marcos.
Aplicar y restaurar tienen sus propios botones; cambiar de vista previa conserva
la aplicación explícita. La entrada escalonada, respuesta de iconos y fundido de
salida se interrumpen al reabrir y respetan la preferencia GTK de movimiento.
# Waybar preferences

All six themes use bottom islands by default. In Style, open the display icon
beside the preview title to choose Bottom/Top/Left/Right and Islands/Full panel. These
preferences are saved independently in `~/.config/desktop-style/waybar.json` and
survive theme changes and restoring the original appearance.
Side panels stack the groups vertically, use compact status icons and a two-line
clock, and reserve space on the selected edge. Tooltips retain the details.
Returning to Top/Bottom restores your horizontal dimensions and module formats.

```sh
desktop-style bar position bottom
desktop-style bar position top
desktop-style bar position left
desktop-style bar position right
desktop-style bar layout islands
desktop-style bar layout continuous
```
