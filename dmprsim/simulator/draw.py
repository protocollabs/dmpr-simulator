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

MAP_TOS_TO_COLOR = {}

link_colors = [
    (255, 0, 0),  # red
    (255, 20, 147),  # pink
    (255, 127, 80),  # coral
    (255, 255, 0),  # yellow
    (189, 183, 107),  # darkkhaki
    (138, 43, 226),  # blueviolet
    (0, 255, 0),  # lime
    (102, 205, 170),  # mediumaquamarin
    (0, 0, 255),  # blue
    (218, 165, 32),  # goldenrod
]
link_colors = [tuple(map(lambda x: x / 255, color)) for color in link_colors]


def draw_images(ld: Path, area, img_idx):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, IMAGE_WIDTH, IMAGE_HEIGHT)
    full_ctx = cairo.Context(surface)
    full_ctx.rectangle(0, 0, IMAGE_WIDTH, IMAGE_HEIGHT)

    # Fill background
    full_ctx.set_source_rgb(0.05, 0.05, 0.05)
    full_ctx.fill()

    draw_frame_info(full_ctx, img_idx)

    # Compute the scale factor and center the main context on the surface
    scale_factor = min(IMAGE_WIDTH / area.width, IMAGE_HEIGHT / area.height)

    x_center_offset = IMAGE_WIDTH / 2 - (area.width * scale_factor / 2)
    y_center_offset = IMAGE_HEIGHT / 2 - (area.height * scale_factor / 2)

    ctx = cairo.Context(surface)
    ctx.translate(x_center_offset, y_center_offset)
    ctx.scale(scale_factor, scale_factor)

    draw_nodes(area, ctx)

    surface.write_to_png(str(ld / 'images' / '{:05}.png'.format(img_idx)))


def draw_frame_info(ctx, img_idx):
    # Add current time in top-left corner
    ctx.set_source_rgba(1., 1., 1., .6)
    ctx.rectangle(10, 10, 40, 20)
    ctx.fill()

    ctx.set_source_rgb(0., .0, .0)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(14)

    ctx.move_to(10, 27)
    ctx.show_text(str(img_idx))

    for i, tos in enumerate(MAP_TOS_TO_COLOR):
        ctx.move_to(10, 47 + 20*i)
        ctx.set_source_rgb(*MAP_TOS_TO_COLOR[tos])
        ctx.show_text(''.join(i[0] for i in tos.split('-')))


def draw_nodes(area, ctx):
    """
    Draw all elements of the final image
    """
    draw_surrounding_rings(area, ctx)
    draw_paths_between_nodes(area, ctx)
    draw_node_circle(area, ctx)
    draw_node_info(area, ctx)


def draw_surrounding_rings(area, ctx):
    """
    Draw the white rings and the red transmission ring around each node

    This is done first so it will be in the background
    """
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
    """
    Draw all paths between nodes

    One path for each link, the exact drawing is handeld in draw_connection.
    Links with a active packet transmission are dashed red.
    """
    ctx.set_source_rgb(1., 1., 1.)
    ctx.set_line_width(1)
    for model in area.models:
        router = model.router
        connections = {}
        for interface_name in router.interfaces.keys():
            for neighbor in router.get_connected_routers(interface_name):
                connections.setdefault(neighbor, []).append(interface_name)

        for neighbor in connections:
            if router.id > neighbor.id:
                continue
            interfaces = sorted(connections[neighbor])

            for i, interface in enumerate(interfaces):
                packets = RouterForwardedPacketMiddleware.get_packets(
                    router, neighbor, interface)
                packets.extend(RouterForwardedPacketMiddleware.get_packets(
                    neighbor, router, interface))
                tos = list(set(packet['tos'] for packet in packets))
                draw_connection(ctx, model.x, model.y,
                                neighbor.model.x, neighbor.model.y,
                                i + 1, len(interfaces),
                                dashed=tos)


rotate_clockwise = np.array(((0, 1), (-1, 0)))


def normalize(vector):
    """
    Normalize a numpy vector
    """
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def draw_connection(ctx, fromx, fromy, tox, toy, idx, num,
                    dashed: list = []):
    """
    Draw a link between the nodes at from(x/y) and to(x/y).

    The offset to the side is defined by idx and num

    :param ctx: Cairo context
    :param fromx: x coordinate origin node
    :param fromy: y coordinate origin node
    :param tox: x coordinate destination node
    :param toy: y coordinate destination node
    :param idx: Index of the link if there are more than one, starts at 1
    :param num: The total amount of links
    :param dashed: bool, if true the line will be dashed red
    """

    # Get vectors from coordinates
    from_ = np.array((fromx, fromy))
    to = np.array((tox, toy))

    # Create a new basis where (1, 0) is equal to the connection vector
    b1 = to - from_
    b2 = rotate_clockwise.dot(b1)  # perpendicular, linear independent vector

    # Compute the matrices for basis changes
    basis_to_context = np.transpose(np.array([b1, b2]))
    basis_to_normalized = np.linalg.inv(basis_to_context)

    # The length of the start and end strips, converted into normalized basis
    normalized_length = np.linalg.norm(
        basis_to_normalized.dot(np.array((10, 0))))

    # Offset of the link to the side of the straight line
    offset = (num - 1) * (-0.5) + (idx - 1) * 1
    start = np.array((2, offset))
    end = np.array((2, -offset))

    # Scale the offsets correctly
    start = normalize(start) * normalized_length * math.sqrt(abs(offset))
    end = normalize(end) * normalized_length * math.sqrt(abs(offset))

    # Handle short connections
    diff = 1 - start[0] - end[0]
    if diff < 0:
        # The connection is shorter than the start and end strips
        # We must cap them
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

    for tos in dashed:
        color = link_colors[hash(tos) % len(link_colors)]
        MAP_TOS_TO_COLOR[tos] = color
        ctx.set_source_rgb(*color)
        ctx.set_dash([hash(tos) % 15 + 1])
        ctx.move_to(*from_)
        ctx.rel_line_to(*basis_to_context.dot(start))
        ctx.rel_line_to(*basis_to_context.dot(line))
        ctx.rel_line_to(*basis_to_context.dot(end))
        ctx.stroke()
    ctx.set_dash([])


def draw_node_circle(area, ctx):
    """
    Draw a circle where the node is
    """
    ctx.set_source_rgb(1., 1., 1.)
    for model in area.models:
        ctx.arc(model.x, model.y, 4, 0, 2 * math.pi)
        ctx.fill()


def draw_node_info(area, ctx):
    """
    Draw a rectangle and the id of the node
    """
    for model in area.models:
        x, y = model.x, model.y
        # The lengths of the line
        xdelta = 10
        ydelta = 10

        # The offset of the rectangle, required if it is left or up of the node
        x_rect = 0
        y_rect = 0

        # The dimensions of the rectangle
        width = 20
        height = 10

        # If there is not enough space right or down of the node, move to the
        # left or up
        if x + xdelta + width > area.width:
            xdelta = -xdelta
            x_rect = -width
        if y + ydelta + height > area.height:
            ydelta = -ydelta
            y_rect = -height

        # Generate text for node, adjust rectangle size
        text = str(model.router.id)
        if model.router.is_transmitter:
            text += " (tx)"
            width += 15
        elif model.router.is_receiver:
            text += " (rx)"
            width += 15

        ctx.set_source_rgba(1., 1., 1., .8)
        ctx.move_to(x, y)
        ctx.line_to(x + xdelta, y + ydelta)
        ctx.stroke()
        ctx.rectangle(x + xdelta + x_rect, y + ydelta + y_rect, width, height)
        ctx.fill()

        ctx.set_source_rgb(0., .0, .0)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(10)
        ctx.move_to(x + xdelta + x_rect, y + ydelta + y_rect + height - 1)

        ctx.show_text(text)


def setup_img_folder(log_directory: Path):
    path = log_directory / 'images'
    shutil.rmtree(str(path), ignore_errors=True)
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        pass
