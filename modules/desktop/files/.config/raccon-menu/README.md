# Menú de escritorio · Eww

Lanzador compacto junto a Waybar: nombre real de la cuenta, foto del sistema cuando existe y seis accesos grandes. No ocupa una ventana del tamaño de la pantalla. El mapache y los accesos a Editor, Fondos y Widgets se retiraron del menú.

- **Inicio:** Navegador, Archivos y Terminal; la segunda fila muestra hasta tres apps de `~/.local/state/raccon-menu/favorites.json` (lista de IDs `.desktop`) que estén instaladas.
- **Búsqueda:** escribe desde cualquier control para buscar inmediatamente. La primera letra se conserva. Enter abre el primer resultado; Tab permite recorrer los controles.
- **Modo PC:** sus cinco opciones están disponibles desde el arranque y después de recargar el tema; panel pequeño al costado. Seleccionar prepara el cambio; **Aplicar** lo ejecuta. La marca identifica el modo realmente activo.
- **Sonido, Wi-Fi y Bluetooth:** desplegables laterales del mismo menú, junto a Modo PC. Incluyen volumen, micrófono, dispositivos, redes, conexión y controles de encendido.
- **Sesión:** panel lateral para bloquear, suspender, cerrar sesión, reiniciar o apagar. Las últimas cuatro acciones requieren confirmación.

`Super` alterna el menú; el lanzador de Waybar permanece oculto. `Esc` cierra primero el panel lateral o borra la búsqueda; después oculta el menú. `Ctrl+1–4` abre Inicio, Apps, Modo PC o Sesión; `Ctrl+F` busca. `Super+L` o `Super+Ctrl+Q` abre Sesión; `Super+Shift+L` bloquea directamente.

```sh
desktop-menu
desktop-menu apps
desktop-menu modes
desktop-menu session
desktop-menu prepare   # daemon y catálogo, sin mostrar una ventana
desktop-menu diagnose  # tamaño, foco, resultados, tiempo del filtro y estado Eww
```

## Rendimiento y movimiento

La ventana y las filas de aplicaciones permanecen en GTK. El catálogo se repone automáticamente al recargar el tema y se actualiza cada cinco minutos. Un FIFO privado gestiona visibilidad y navegación; escribir filtra directamente las filas sin lanzar Python ni reconstruir el catálogo por tecla. Enter usa los resultados visibles de la consulta actual. Las palabras se comparan literalmente, sin distinguir mayúsculas ni acentos y sin interpretarlas como comandos.

La apertura usa un fundido breve sin redimensionar la ventana, la búsqueda cambia de vista y los paneles aparecen al costado. Ahorro y Working conservan transiciones breves de 140 ms; otros perfiles permiten 220 ms. La preferencia GTK `gtk-enable-animations=false` elimina el movimiento. No hay animaciones ambientales ni consultas de música, CPU o RAM. La música vive en el widget flotante `~/.config/raccon-music`.

Wayfire ejecuta `prepare` al iniciar y construye la ventana oculta, incluidos catálogo y controles, antes de la primera apertura. La primera apertura tras cambiar el módulo renueva únicamente la instancia del menú. Eww 0.5 puede completar una apertura aunque su respuesta IPC expire: el controlador confirma la ventana antes de recurrir al respaldo.

## Cuenta y temas

El nombre procede de AccountsService o del registro de la cuenta. La foto procede de AccountsService, `~/.face` o `~/.face.icon`; si no existe, se oculta por completo. No hay avatar de reemplazo.

`~/.config/waybar/colors.css` es la autoridad de color; `~/.config/eww/_colors.scss` es respaldo. El proveedor genera `_palette.scss` al cambiar el tema o el nivel de batería. El contorno usa los mismos roles y opacidades que Waybar: `outline_variant` normalmente y el rol configurado en `desktop-power/config.toml` para batería alta, baja o crítica. El fondo tiene mayor opacidad para conservar la lectura sobre otras ventanas.

## Widgets y paneles

Los widgets propios y tinyWidgets siguen en `~/.config/eww`, administrados por `widgetctl`. Quitar su acceso del menú no los elimina. El menú y todos sus desplegables comparten una única instancia Eww en `~/.config/raccon-menu`. `controls.yuck` contiene Sonido, Wi-Fi y Bluetooth; sus proveedores consultan el servicio correspondiente cuando está abierto su desplegable. No se inicia otra ventana de controles. El calendario abre como panel lateral de la misma ventana y conserva la agenda de `~/.local/share/desktop-menu/events.json` y las tareas de hoy. El respaldo anterior sigue disponible con `desktop-panel --legacy calendar`.

```sh
eww -c "$HOME/.config/raccon-menu" reload
desktop-menu --legacy
```

## Validación

Las pruebas cubren el FIFO, revisiones del módulo, búsqueda nativa con acentos y caracteres de shell, primera letra, Enter, selección real de vistas GTK, confirmaciones, modos, colores y recuperación IPC. La prueba GTK opcional no muestra ninguna ventana ni abre aplicaciones:

```sh
RACCON_MENU_GUI_TEST=1 python3 -B -m unittest discover -s tests -p test_menu_native.py -v
```

En Wayfire se verificaron el popup compacto, escritura real y transiciones de apertura. El filtro sobre 58 aplicaciones midió aproximadamente 0,1–1,9 ms; esto mide el filtro, no el fotograma completo. El registro está en `~/.local/state/raccon-menu/daemon.log`.

## Gestor de acceso

`desktop-login-sddm --check` muestra el gestor predeterminado y otros gestores habilitados. El instalador de dots no cambia gestores automáticamente. El estado comprobado al completar este cambio usa SDDM y no tiene otros gestores habilitados.

## Junto a Waybar

El menú sigue la posición real de Waybar (`bottom`, `top`, `left`, `right`) y conserva una separación de 4 píxeles. El adaptador nativo evita descontar dos veces el área reservada por la barra. Los desplegables de Sonido, Wi-Fi y Bluetooth forman parte de la misma ventana y conservan este posicionamiento.

## Controles integrados

Los botones Sonido, Wi-Fi y Bluetooth abren el lateral igual que Modo PC; al pulsar de nuevo se recoge. Solo se muestra un desplegable a la vez. La separación lateral es de 4 píxeles.

```sh
desktop-menu audio
desktop-menu connections
desktop-menu bluetooth
# Los accesos de Waybar conservan sus comandos habituales:
desktop-panel audio
desktop-panel connections
desktop-panel bluetooth
```

`desktop-panel` es un acceso de compatibilidad a Raccon Menu, sin daemon ni ventana propios. Su antiguo autostart se retiró. El respaldo anterior permanece disponible mediante `desktop-panel --legacy audio` y su calendario mediante `desktop-panel --legacy calendar`.

Sonido incluye salida, micrófono, volumen, silenciamiento y selección de dispositivos. Wi-Fi permite buscar, conectar y desconectar; la contraseña queda oculta, se vacía al cerrar/cambiar de desplegable o enviarla, y viaja por stdin sin shell ni archivos. Wi-Fi y Bluetooth aprovechan toda la altura lateral. Las listas muestran cuatro opciones por página, sin desplazamiento anidado; las flechas permiten recorrer el resto sin volver a consultar las radios. La conexión Wi-Fi abre su propio formulario con seguridad, señal y contraseña, y **Redes** devuelve a la lista.

Bluetooth conserva encendido y búsqueda. Seleccionar un dispositivo abre su ficha con estado, tipo, dirección, señal y batería, y un botón explícito para conectar o desconectar. La batería muestra **Sin datos** si el dispositivo no comunica su porcentaje. La ficha se actualiza mientras está abierta; el emparejamiento con PIN requiere una herramienta compatible.

La prueba `python3 tests/check_docking_installed.py` verifica con una Waybar real en un compositor privado los cuatro bordes y que los accesos de servicios abran una única ventana Raccon Menu. Comprueba también listas con nombres largos, formulario Wi-Fi con contraseña visible y ficha Bluetooth: cero desbordamientos y cero contenedores de scroll en ambas vistas. No cambia conexiones ni volumen.

## Movimiento

La capa de movimiento va al final de `eww.scss`, después de `desktop-style`, porque el tema pone `transition: none` en botones y paneles. Al abrir, `input.c` pone `enter` (pose inicial) durante un fotograma y `entering` (retrasos escalonados) mientras dura la entrada, solo en cabecera, búsqueda, apps diarias, utilidades y navegación: cambiar la clase en la raíz reestilizaba todo el árbol (~40 ms). Con `desktop.motion` en falso (`.still`) no hay animación. Tras arrancar o recargar, la ventana se muestra y oculta dos veces de forma invisible para que la primera apertura real no tenga el tirón de ~120 ms de GTK.

## Teclado compartido

- Flechas: mover el foco según la posición de los controles. En campos de texto y sliders conservan su función nativa. Desde búsqueda, ↓ entra a los resultados o accesos de Inicio.
- Tab / Shift+Tab: recorrer todos los controles. Enter / Espacio: activar el enfocado; mantener la tecla no repite la activación de botones.
- Ctrl+1…8: Inicio, Apps, Modo PC, Sesión, Sonido, Wi-Fi, Bluetooth, Calendario. Ctrl+F / Ctrl+L: búsqueda. Alt+1…9: lanzar el acceso de Inicio correspondiente.
- Esc conserva el retroceso contextual del menú; Ctrl+W lo cierra directamente.
- Adaptador compartido: `~/.local/lib/raccon_menu/navigation.h`. Sus cambios invalidan la revisión del módulo residente y fuerzan recompilación al abrir. `test_keyboard.py` verifica selección direccional y revisión; la interacción GTK completa requiere sesión gráfica.

## Calendario integrado

Clic en el reloj o `desktop-panel calendar` abre el calendario junto al menú.
Elige un día, escribe un evento y pulsa Enter o +; el texto se envía por stdin.
Se conservan los eventos existentes, próximos eventos y las tareas de hoy.
La agenda usa escrituras atómicas con bloqueo; un archivo dañado nunca se
reemplaza por una agenda vacía. La consulta de tareas solo corre con el panel abierto.

## Compact English controls

Raccon's menu, service panels, calendar, floating wallpaper/session cards and music
controls use English UI text. Navigation, shortcuts and routine actions use icons
with tooltips; app search results, device names, errors and destructive confirmation
questions retain the text needed to identify the target and outcome. This changes
Raccon's interface language, not the desktop session locale or user content.
# Compact layout and calendar

The launcher and attached service pages size to their contents. Wi-Fi and
Bluetooth retain pagination for longer lists; their actions no longer fill a
full-height side panel. Audio expands device choices only when requested.

The Calendar button (or Ctrl+8) opens a six-week grid with explicit ISO dates,
month navigation, a today shortcut and event markers. Event storage remains
`~/.local/share/desktop-menu/events.json`. Month changes clamp to valid days,
including leap years. Adding an event captures the visible selected date.

The menu slides from the live Waybar edge in 240 ms and returns in 160 ms.
GTK's disabled animations turn it off; savings/Working retain a brief 140 ms entry.
The resident surface retains its allocation during the animation.
