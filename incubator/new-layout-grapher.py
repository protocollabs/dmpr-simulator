#!/usr/bin/env python

import math
import cairo

WIDTH, HEIGHT = 1024, 1024

surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
ctx = cairo.Context (surface)

ctx.scale(WIDTH, HEIGHT)
ctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)

ctx.set_source_rgb (0.05, 0.05, 0.05)
ctx.rectangle (0, 0, 1, 1)
ctx.fill ()

# surrounding lines arc 1
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

# surrounding lines arc 2
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


ctx.set_line_width(0.0015)
# #42A5F5 -> http://corecoding.com/utilities/rgb-or-hex-to-float.php
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

# circles now

ctx.set_source_rgb(1., 1., 1.)
ctx.arc(0.01, 0.5, .004, 0, 2 * math.pi)
ctx.fill()


ctx.set_source_rgb(1., 1., 1.)
ctx.arc(0.99, .5, .004, 0, 2 * math.pi)
ctx.fill()

surface.write_to_png ("new-layout.png")
