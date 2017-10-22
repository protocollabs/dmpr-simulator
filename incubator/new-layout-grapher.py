#!/usr/bin/env python

import math
import cairo

# Hex to RGB Float converter:
#   http://corecoding.com/utilities/rgb-or-hex-to-float.php

# 4K: 4096 x 2160
WIDTH, HEIGHT = 1000, 1000


def init():
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)

    ctx.scale(WIDTH, HEIGHT)
    ctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)

    ctx.set_source_rgb(0.05, 0.05, 0.05)
    ctx.rectangle(0, 0, 1, 1)
    ctx.fill()

    return ctx, surface

def draw_surrounding_rings(ctx):
    # surrounding lines node 1
    ctx.set_line_width(0.0005)
    ctx.set_source_rgba(1., 1., 1.)
    ctx.arc(0.01, 0.5, .008, 0, 2 * math.pi)
    ctx.stroke()

    ctx.set_line_width(0.0003)
    ctx.set_source_rgba(1., 1., 1.)
    ctx.arc(0.01, 0.5, .012, 0, 2 * math.pi)
    ctx.stroke()

    ctx.set_line_width(0.0001)
    ctx.set_source_rgba(1., 1., 1.)
    ctx.arc(0.01, 0.5, .015, 0, 2 * math.pi)
    ctx.stroke()

    # surrounding lines node 2
    ctx.set_line_width(0.0005)
    ctx.set_source_rgba(1., 1., 1.)
    ctx.arc(0.99, .5, .008, 0, 2 * math.pi)
    ctx.stroke()

    ctx.set_line_width(0.0003)
    ctx.set_source_rgba(1., 1., 1.)
    ctx.arc(0.99, .5, .012, 0, 2 * math.pi)
    ctx.stroke()

    ctx.set_line_width(0.0001)
    ctx.set_source_rgba(1., 1., 1.)
    ctx.arc(0.99, .5, .015, 0, 2 * math.pi)
    ctx.stroke()


def draw_paths_between_nodes(ctx):
    ctx.set_line_width(0.0015)
    ctx.set_source_rgb(0.259, 0.647, 0.961)

    ctx.move_to(0.01, 0.5)
    ctx.curve_to(0.25, 0.48, 0.75, 0.48, 0.99, .5)
    ctx.stroke()

    ctx.move_to(0.01, 0.5)
    ctx.curve_to(0.25, 0.52, 0.75, 0.52, 0.99, .5)
    ctx.stroke()

    ctx.move_to(0.01, 0.5)
    ctx.line_to(0.99, .5)
    ctx.stroke()


def draw_node_circle(ctx):
    ctx.set_source_rgb(1., 1., 1.)
    ctx.arc(0.01, 0.5, .004, 0, 2 * math.pi)
    ctx.fill()

    ctx.set_source_rgb(1., 1., 1.)
    ctx.arc(0.99, .5, .004, 0, 2 * math.pi)
    ctx.fill()

def draw_node_info(ctx):
    ctx.set_source_rgba(1., 1., 1., .9)

    ctx.move_to(0.01, 0.5)
    ctx.line_to(0.03, 0.55)
    ctx.stroke()

    ctx.rectangle(0.03, 0.55, .04, .02)
    ctx.fill()

    # text
    ctx.set_source_rgb(0., .0, .0)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(.01);
    ctx.move_to(0.032, 0.565);
    ctx.show_text("23");


def generate_image(surface):
    surface.write_to_png("new-layout.png")


ctx, surface = init()
draw_surrounding_rings(ctx)
draw_paths_between_nodes(ctx)
draw_node_circle(ctx)
draw_node_info(ctx)
generate_image(surface)


