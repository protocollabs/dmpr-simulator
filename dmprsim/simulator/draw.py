import math
import shutil
from pathlib import Path

import numpy as np

try:
    import cairo
except ImportError:
    import cairocffi as cairo

from .middlewares import RouterForwardedPacketMiddleware, \
    RouterTransmittedMiddleware

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080


def draw_images(ld: Path, area, img_idx):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, IMAGE_WIDTH, IMAGE_HEIGHT)
    full_ctx = cairo.Context(surface)
    full_ctx.rectangle(0, 0, IMAGE_WIDTH, IMAGE_HEIGHT)
    full_ctx.set_source_rgb(0.05, 0.05, 0.05)
    full_ctx.fill()
    full_ctx.set_source_rgba(1., 1., 1., .8)
    full_ctx.rectangle(10, 10, 40, 20)
    full_ctx.fill()
    full_ctx.move_to(10, 27)

    full_ctx.set_source_rgb(1., .0, .0)
    full_ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                              cairo.FONT_WEIGHT_NORMAL)
    full_ctx.set_font_size(15)
    full_ctx.show_text(str(img_idx))

    scale_factor = min(IMAGE_WIDTH / area.width, IMAGE_HEIGHT / area.height)

    x_center_offset = IMAGE_WIDTH / 2 - (area.width * scale_factor / 2)
    y_center_offset = IMAGE_HEIGHT / 2 - (area.height * scale_factor / 2)

    # One context on the left, scaled to half the width and full height
    # and centered on x- and y-axis
    ctx = cairo.Context(surface)
    ctx.translate(x_center_offset, y_center_offset)
    ctx.scale(scale_factor, scale_factor)

    draw_nodes(area, ctx)

    surface.write_to_png(str(ld / 'images' / '{:05}.png'.format(img_idx)))


def draw_nodes(area, ctx):
    draw_surrounding_rings(area, ctx)
    draw_paths_between_nodes(area, ctx)
    draw_node_circle(area, ctx)
    draw_node_info(area, ctx)


def draw_surrounding_rings(area, ctx):
    for model in area.models:
        ctx.set_line_width(0.5)
        ctx.set_source_rgba(1., 1., 1.)
        ctx.arc(model.x, model.y, 8, 0, 2 * math.pi)
        ctx.stroke()

        ctx.set_line_width(0.3)
        ctx.set_source_rgba(1., 1., 1.)
        ctx.arc(model.x, model.y, 12, 0, 2 * math.pi)
        ctx.stroke()

        ctx.set_line_width(0.1)
        ctx.set_source_rgba(1., 1., 1.)
        ctx.arc(model.x, model.y, 15, 0, 2 * math.pi)
        ctx.stroke()

        if model.router in RouterTransmittedMiddleware.transmitting_routers:
            ctx.set_line_width(1)
            ctx.set_source_rgb(1., 0., 0.)
            ctx.arc(model.x, model.y, 15, 0, 2 * math.pi)
            ctx.stroke()


def draw_paths_between_nodes(area, ctx):
    ctx.set_source_rgb(1., 1., 1.)
    ctx.set_line_width(1)
    for model in area.models:
        router = model.router
        connections = {}
        for interface_name in router.interfaces.keys():
            for neighbor in router.get_connected_routers(interface_name):
                connections.setdefault(neighbor, []).append(interface_name)

        for neighbor in connections:
            interfaces = sorted(connections[neighbor])

            for i, interface in enumerate(interfaces):
                dashed = RouterForwardedPacketMiddleware.has_transmitted(
                    router, neighbor, interface) or \
                         RouterForwardedPacketMiddleware.has_transmitted(
                             neighbor, router, interface)
                draw_connection(ctx, model.x, model.y,
                                neighbor.model.x, neighbor.model.y,
                                i + 1, len(interfaces),
                                dashed=dashed)


rotate_clockwise = np.array(((0, 1), (-1, 0)))


def normalize(vector):
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def draw_connection(ctx, fromx, fromy, tox, toy, idx, num, dashed=False):
    # Get vectors from coordinates
    from_ = np.array((fromx, fromy))
    to = np.array((tox, toy))

    # Create a new basis where (1, 0) is equal to the connection vector
    b1 = to - from_
    b2 = rotate_clockwise.dot(b1)  # perpendicular, linear independent vector

    # Compute the matrices for basis changes
    basis_to_context = np.transpose(np.array([b1, b2]))
    basis_to_normalized = np.linalg.inv(basis_to_context)

    # The length, converted into the "normalized" basis
    normalized_length = np.linalg.norm(
        basis_to_normalized.dot(np.array((10, 0))))

    offset = (num - 1) * (-0.5) + (idx - 1) * 1

    start = np.array((2, offset))
    end = np.array((2, -offset))

    start = normalize(start) * normalized_length * math.sqrt(abs(offset))
    end = normalize(end) * normalized_length * math.sqrt(abs(offset))

    # Handle short connections and the length of start and end strips
    diff = 1 - start[0] - end[0]
    if diff < 0:
        # We must cap the start and end strips
        start /= start[0] - diff / 2
        end /= end[0] - diff / 2
        # Also we don't need a line between them as they are directly next to
        # each other
        line = (0, 0)
    else:
        # The line is the remaining bit between the start and end strips
        line = np.array((diff, 0))

    # Draw
    ctx.set_source_rgb(0.259, 0.647, 0.961)
    ctx.move_to(*from_)
    ctx.rel_line_to(*basis_to_context.dot(start))
    ctx.rel_line_to(*basis_to_context.dot(line))
    ctx.rel_line_to(*basis_to_context.dot(end))
    ctx.stroke()

    if dashed:
        ctx.set_source_rgb(1., 0., 0.)
        ctx.set_dash([10])
        ctx.move_to(*from_)
        ctx.rel_line_to(*basis_to_context.dot(start))
        ctx.rel_line_to(*basis_to_context.dot(line))
        ctx.rel_line_to(*basis_to_context.dot(end))
        ctx.stroke()
    ctx.set_dash([])


def draw_node_circle(area, ctx):
    ctx.set_source_rgb(1., 1., 1.)
    for model in area.models:
        ctx.arc(model.x, model.y, 4, 0, 2 * math.pi)
        ctx.fill()


def draw_node_info(area, ctx):
    for model in area.models:
        ctx.set_source_rgba(1., 1., 1., .8)
        x, y = model.x, model.y
        xdelta = 10
        ydelta = 10
        x_rect = 0
        y_rect = 0
        width = 20
        height = 10
        if x + xdelta + width > area.width:
            xdelta = -xdelta
            x_rect = -width
        if y + ydelta + height > area.height:
            ydelta = -ydelta
            y_rect = -height
        ctx.move_to(model.x, model.y)
        ctx.line_to(x + xdelta, y + ydelta)
        ctx.stroke()
        ctx.rectangle(x + xdelta + x_rect, y + ydelta + y_rect, width, height)
        ctx.fill()

        ctx.set_source_rgb(0., .0, .0)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(10)
        ctx.move_to(x + xdelta + x_rect, y + ydelta + y_rect + height - 1)
        ctx.show_text(str(model.router.id))


def setup_img_folder(log_directory: Path):
    path = log_directory / 'images'
    shutil.rmtree(str(path), ignore_errors=True)
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        pass
