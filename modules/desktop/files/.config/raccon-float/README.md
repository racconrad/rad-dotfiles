# Widgets flotantes grandes · Eww

Dos tarjetas centradas, sin brillos. Siguen el tema activo de `desktop-style`: paleta de `raccon-menu/_palette.scss` y forma desde `desktop-style/current/tokens.json` (radio, radio de controles, borde, opacidad, fuente, rellenos). `raccon-float` reescribe `_tokens.scss` solo cuando esos tokens cambian; Terminal queda recto con borde de 1 px, los estilos redondeados quedan redondeados.

```sh
raccon-float wallpaper   # Super+W · fondos: galería mixta con filtros Todos / Imágenes / Videos, clic aplica (wallpaper-set)
raccon-float session     # Super+Ctrl+Q · bloquear, suspender, salir, reiniciar, apagar
raccon-float close
```

- Fondos: cuadrícula de 4 × 3, scroll vertical continuo, sin nombres, tooltips ni overlays. El hover expande solo en X con rebote contenido; las vecinas compensan el ancho, también en filas incompletas. Altura fija de 154 px e imagen pintada a tamaño fijo para revelar el recorte sin reescalarlo en cada fotograma. La pulsación responde con opacidad. La tarjeta y su contenido aparecen por opacidad, sin revelar cada fila por separado.
- Miniaturas: se preparan las del filtro activo, con dos trabajadores y un hilo FFmpeg por proceso. Caché publicada atómicamente; timeout por intento de 8 s. Se reutilizan las miniaturas existentes. Las pestañas no instancian las dos colecciones a la vez.
- Sesión: Bloquear es inmediato; el resto se arma con un clic (se ensancha, el icono hace un gesto breve, Apagar/Reiniciar en rojo) y se ejecuta con el segundo.
- Datos: `~/.local/lib/raccon_menu/walls.py` (miniaturas en `~/.cache/raccon-float/thumbs`, `WALLPAPER_DIR`, por defecto `@RDOT_HOME@/Pictures/Wallpapers`). Las tiles usan índice, nunca la ruta, en comandos.
- Todo el estilo propio va después de `_desktop-style.scss` a propósito: el tema pone contornos, esquinas rectas y `transition: none` en los botones de los popups.
- Instancia Eww propia: el módulo nativo de Raccon Menu toma cualquier ventana de su instancia como el menú.
- Atajos anteriores (`wallpaper-grid`, `desktop-menu session`): copia en `~/.local/state/wayfire.ini.bak-raccon-float`.

- `desktop-style` ejecuta `raccon-float refresh` al publicar el tema: actualiza tokens y recarga los imports compartidos también con la tarjeta abierta. La preferencia GTK de animaciones se comparte con Raccon Menu; desactivarla elimina transiciones y gestos.

Pruebas sin escritorio: `python3 ~/.config/raccon-float/test_walls.py`.

- La galería abre con Todos, ordenando imágenes y videos juntos por nombre. Los filtros conservan la misma cuadrícula desplazable. Cerrar con X desvanece la tarjeta completa antes de ocultarla; el cuerpo se reinicia solo después, sin encoger la ventana centrada.

- Videos: la miniatura se reproduce automáticamente al pasar el cursor o enfocarla con el teclado; al salir se detiene. Un icono de video identifica estos fondos. Hay una espera de 180 ms para evitar decodificar al cruzar rápidamente la cuadrícula. Solo una miniatura se anima a la vez: fragmento de 4 s a 12 fps, en caché, sin audio. No hay reproductor adicional ni ventana externa. Clic o Enter en la miniatura aplica el fondo.

- La X mide 32 × 32, centrada verticalmente, sin rotación ni escalado.
- Sesión: Super+Ctrl+Q o clic en ⏻ de Waybar abre `raccon-float session`. Waybar ya no usa `waybar-power-hold press/release`; las acciones sensibles mantienen la confirmación de dos clics dentro de la tarjeta.

## Teclado

Flechas mueven el foco; Tab/Shift+Tab recorren controles; Enter/Espacio activan. El foco tiene un contorno visible y la galería desplaza el scroll para seguirlo. Inicio/Fin van al primer/último fondo o acción; RePág/AvPág avanzan tres pasos verticales.

Fondos: Ctrl+1 Todos, Ctrl+2 Imágenes, Ctrl+3 Videos. El foco inicia la vista previa del video automáticamente; P permite iniciarla otra vez después de detenerla. Esc cierra primero la vista previa y después la tarjeta; Ctrl+W cierra directamente.

Sesión: Ctrl+1…5 enfoca Bloquear/Suspender/Salir/Reiniciar/Apagar sin ejecutarlos. Enter arma la acción, otro Enter tras soltar confirma. Esc cancela lo armado antes de cerrar. Mantener Enter/Espacio no confirma por repetición.

`float_input.c` usa el adaptador GTK compartido; el launcher compila y renueva solo su propia instancia Eww cuando cambia. Música reutiliza este adaptador para flechas, Tab, Enter/Espacio y Esc/Ctrl+W.

## Reproducción y foco optimizados

Los fotogramas ya no pasan por una variable de Eww a 12 Hz. `thumbnail_playback.h` carga una vez los 48 JPEG pequeños y dibuja únicamente la miniatura activa desde GTK. Solo los cambios de selección/estado se envían al árbol de Eww; al detener/cambiar se liberan los pixbufs. Ratón y teclado comparten `expanded-row` / `expanded-tile`, conservando ancho total y altura fija. La expansión dura 280 ms sin sobrepasar el tamaño final. El contorno del foco permanece visible sobre el video.
