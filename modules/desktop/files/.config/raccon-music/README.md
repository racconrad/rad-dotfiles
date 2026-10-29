# Música flotante · Eww

Tarjeta flotante compacta junto a Waybar: carátula, título, artista, pausa, barra de progreso fina y **×**, que la oculta por completo. Mientras está abierta, Waybar no muestra música; cerrada, Waybar muestra botones compactos: 󰝚 abre la tarjeta (clic derecho enfoca el reproductor), anterior, pausa y siguiente. Al pasar el ratón muestra tiempo, anterior y siguiente. Se vacía si no hay reproductor MPRIS.

```sh
raccon-music   # abre o cierra la tarjeta (también: 󰝚 en Waybar)
raccon-music close
```

- Datos: un único `playerctl --follow` en `~/.local/lib/raccon_menu/music.py`, sin consultas periódicas. Carátulas remotas en `~/.cache/raccon-menu/art`.
- Tema: importa `_palette.scss` y `_desktop-style.scss` de `~/.config/raccon-menu`; superficie, borde, radio y botones siguen el estilo activo. `raccon-music` recarga la instancia si esos archivos cambiaron.
- Waybar: `waybar-music open|prev|play|next`, un `playerctl --follow status` por botón; se vacían sin reproductor o con la tarjeta abierta (`$XDG_RUNTIME_DIR/raccon-music.open`).
- Instancia Eww propia: el módulo nativo de Raccon Menu toma cualquier ventana de su instancia como el menú.

Teclado: flechas o Tab/Shift+Tab para enfocar controles; Enter/Espacio activa; Esc o Ctrl+W cierra.
