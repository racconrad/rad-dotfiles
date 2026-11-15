#pragma once

#include "hud-model.hpp"
#include <wayfire/plugins/common/cairo-util.hpp>
#include <array>
#include <cmath>

namespace snap
{
class selector_view
{
    std::shared_ptr<wf::texture_t> texture;
    bool dirty = true;
    unsigned pattern = 0, slot = 0;
    std::string message;
    box bounds{0, 0, 0, 0};

    static void rounded(cairo_t *cr, box b, double radius)
    {
        radius = std::min({radius, b.width / 2.0, b.height / 2.0});
        const double pi = std::acos(-1.0);
        cairo_new_sub_path(cr);
        cairo_arc(cr, b.x + b.width - radius, b.y + radius, radius, -pi / 2, 0);
        cairo_arc(cr, b.x + b.width - radius, b.y + b.height - radius, radius, 0, pi / 2);
        cairo_arc(cr, b.x + radius, b.y + b.height - radius, radius, pi / 2, pi);
        cairo_arc(cr, b.x + radius, b.y + radius, radius, pi, pi * 1.5);
        cairo_close_path(cr);
    }

    static void text(cairo_t *cr, double x, double y, int width, const std::string& value,
        bool muted = false, bool title = false)
    {
        auto layout = pango_cairo_create_layout(cr);
        auto font = pango_font_description_from_string(title ? "Inter Semi-Bold 14" : "Inter 10");
        pango_layout_set_font_description(layout, font);
        pango_layout_set_text(layout, value.c_str(), -1);
        pango_layout_set_width(layout, std::max(1, width) * PANGO_SCALE);
        pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_END);
        cairo_set_source_rgb(cr, muted ? .70 : .95, muted ? .74 : .96, muted ? .80 : .98);
        cairo_move_to(cr, x, y);
        pango_cairo_show_layout(cr, layout);
        pango_font_description_free(font);
        g_object_unref(layout);
    }

    void update_texture(const selector_layout& ui)
    {
        auto surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, ui.panel.width, ui.panel.height);
        auto cr = cairo_create(surface);
        cairo_translate(cr, -ui.panel.x, -ui.panel.y);
        rounded(cr, ui.panel, 16);
        cairo_set_source_rgba(cr, .085, .095, .12, .98);
        cairo_fill_preserve(cr);
        cairo_set_source_rgba(cr, .52, .57, .66, .65);
        cairo_set_line_width(cr, 1);
        cairo_stroke(cr);
        text(cr, ui.panel.x + 16, ui.panel.y + 12, ui.panel.width - 32, "Snap window", false, true);
        const std::array<std::string, 6> names = {"1  Halves", "2  Wide right", "3  Thirds", "4  Rows", "5  Tall top", "6  Grid"};
        for (unsigned i = 0; i < names.size() && ui.usable(); ++i)
        {
            auto card = ui.card(i);
            rounded(cr, card, 8);
            cairo_set_source_rgb(cr, i == pattern ? .18 : .12, i == pattern ? .22 : .135, i == pattern ? .29 : .17);
            cairo_fill(cr);
            text(cr, card.x + 8, card.y + 5, card.width - 16, names[i], i != pattern);
            auto cells = ui.slots(i);
            for (unsigned j = 0; j < cells.size(); ++j)
            {
                const bool selected = i == pattern && j == slot;
                rounded(cr, cells[j], 3);
                cairo_set_source_rgb(cr, selected ? .62 : .29, selected ? .75 : .33, selected ? .97 : .41);
                cairo_fill(cr);
            }
        }
        const bool error = !message.empty();
        text(cr, ui.panel.x + 16, ui.panel.y + ui.panel.height - 28, ui.panel.width - 32,
            !ui.usable() ? "Screen too small for Snap · Esc to close" :
            (error ? message : "1–6 layout · Arrows zone · Enter apply · Esc cancel"), !error);
        cairo_destroy(cr);
        cairo_surface_flush(surface);
        wf::owned_texture_t uploaded(surface);
        texture = uploaded.get_texture();
        cairo_surface_destroy(surface);
        dirty = false;
    }

  public:
    void set_selection(unsigned next_pattern, unsigned next_slot, const std::string& next_message)
    {
        dirty |= pattern != next_pattern || slot != next_slot || message != next_message;
        pattern = next_pattern;
        slot = next_slot;
        message = next_message;
    }

    void clear() { texture.reset(); dirty = true; }

    void render(wf::render_pass_t& pass, const selector_layout& ui)
    {
        dirty |= bounds.x != ui.panel.x || bounds.y != ui.panel.y ||
            bounds.width != ui.panel.width || bounds.height != ui.panel.height;
        bounds = ui.panel;
        if (dirty) update_texture(ui);
        if (!texture) return;
        wf::geometry_t geometry{double(bounds.x), double(bounds.y), double(bounds.width), double(bounds.height)};
        pass.add_texture(texture, pass.get_target(), geometry, wf::regionf_t{geometry});
    }
};
}
