# Estilo del escritorio: Collage

Raccon Dots utiliza un estilo visual único y predeterminado: **Collage**, inspirado
en recortes de papel maximalistas y estética gráfica editorial (Vocaloid / UTAU).
La forma, tipografía y estructura de superficies son fijas, mientras que los colores
se adaptan dinámicamente al fondo de pantalla activo mediante extracción Material You con Matugen.

## Características visuales

- **Superficies angulares**: Chaflanes rectos y asimétricos con bordes contrastados (`2px`), sombras gráficas sólidas sin desenfoque (`box-shadow: 3px 3px 0`).
- **Paleta triádica armónica**: `collage.py` deriva tonos primarios, secundarios y terciarios a partir del fondo de pantalla vigente, garantizando un contraste visual estricto (WCAG ≥ 4.8).
- **Tipografía**: Fuente de titulares y display legible (`Inter Display` / `Inter`), integrada en los widgets de Quickshell, menús del sistema, tarjetas flotantes y notificaciones.
- **Integración global**: Modifica coordinadamente Rofi, Raccon Menu, marcos de ventana en Hyprland, notificaciones SwayNC, SwayOSD, Gtklock y temas de terminales (Kitty, Fuzzel).

## Comandos disponibles

El script `desktop-style` administra la aplicación cromática y las preferencias de superficie:

- `desktop-style apply [collage]`: Re-aplica la configuración del estilo Collage y sincroniza los tokens con el entorno gráfico.
- `desktop-style wallpaper`: Detecta cambios en el fondo de pantalla vigente, extrae la nueva paleta y actualiza los archivos dependientes. Se invoca automáticamente desde `wallpaper-theme`.
- `desktop-style sddm`: Prepara y publica la paleta actual en el tema de inicio de sesión SDDM mediante autenticación interactiva (`pkexec`).
- `desktop-style reset`: Restaura la configuración previa de colores y superficies.
- `desktop-style status`: Muestra en formato JSON el estado y metadatos del estilo activo.

## Arquitectura y archivos

- **Motor Python**: `~/.local/lib/desktop_style/main.py` y sus submódulos (`apply.py`, `appearance.py`, `launchers.py`, `collage.py`, `collage_surfaces.py`, `colors.py`, `frames.py`, `helpers.py`, `pipeline.py`, `sddm.py`).
- **Tokens y estilos generados**: `~/.config/desktop-style/current/tokens.json`, junto con las hojas CSS/SCSS especializadas para cada componente del escritorio (`raccon.scss`, `rofi.rasi`, `swaync.css`, `swayosd.css`, etc.).
- **Paleta de origen**: `~/.config/matugen/out/desktop-style-source.json`.
