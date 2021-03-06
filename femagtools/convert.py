# -*- coding: utf-8 -*-
"""
    femagtools.convert
    ~~~~~~~~~~~~~~~~~~

    Covert FEMAG files to various unstructured grid file formats
"""
import logging
import meshio
import numpy as np
from femagtools import isa7
from collections import defaultdict

logger = logging.getLogger('femagtools.convert')


def _from_isa(isa, filename, target_format, extrude=0, layers=0, recombine=False):

    if not isa.FC_RADIUS:
        logger.warn("airgap radius is not set in source file")

    airgap_center_elements = []
    for e in isa.elements:
        outside = [np.sqrt(v.x**2 + v.y**2) > isa.FC_RADIUS
                   for v in e.vertices]
        if any(outside) and not all(outside):
            airgap_center_elements.append(e)

    airgap_center_vertices = [v for e in airgap_center_elements
                              for v in e.vertices]

    airgap_rotor_elements = []
    airgap_stator_elements = []
    for e in isa.elements:
        if e in airgap_center_elements:
            continue
        for v in e.vertices:
            if v not in airgap_center_vertices:
                continue
            if np.sqrt(v.x**2 + v.y**2) > isa.FC_RADIUS:
                airgap_stator_elements.append(e)
                break
            else:
                airgap_rotor_elements.append(e)
                break

    airgap_stator_vertices = [v for e in airgap_stator_elements
                              for v in e.vertices]

    airgap_lines = []
    for e in airgap_center_elements:
        ev = e.vertices
        for i, v1 in enumerate(ev):
            v2 = ev[i-1]
            if v1 in airgap_stator_vertices and \
               v2 in airgap_stator_vertices:
                airgap_lines.append((v1, v2))

    nodechain_links = defaultdict(list)
    for nc in isa.nodechains:
        nodechain_links[nc.node1].extend(nc.nodes)
        nodechain_links[nc.node2].extend(nc.nodes)
        if nc.nodemid is not None:
            nodechain_links[nc.nodemid].extend(nc.nodes)

    physical_lines = ["v_potential_0",
                      "v_potential_const",
                      "periodic_+",
                      "periodic_-",
                      "infinite_boundary",
                      "no_condition",
                      "Airgap"]

    physical_surfaces = sorted(set([sr.name
                                    for sr in isa.subregions]
                                   + ["Winding_{}_{}".format(w.key, pol)
                                      for w in isa.windings
                                      for pol in ("+", "-")]
                                   + ["Air_Rotor",
                                      "Air_Stator",
                                      "Airgap_Rotor",
                                      "Airgap_Stator",
                                      "PM1", "PM2",
                                      "PM3", "PM4"]))

    def physical_line(n1, n2):
        if (n1, n2) in airgap_lines or (n2, n1) in airgap_lines:
            return 7  # airgap
        if n1.bndcnd == n2.bndcnd:
            return boundary_condition(n1)
        if boundary_condition(n1) == 1:
            return boundary_condition(n2)
        return boundary_condition(n1)

    def boundary_condition(node):
        if node.bndcnd == 0:
            return 6  # no condition
        if node.bndcnd == 1:
            return 1  # vpot 0
        if node.bndcnd == 2:
            return 2  # vpot const
        if node.bndcnd == 3 or node.bndcnd == 6:
            return 4  # periodic -
        if node.bndcnd == 4 or node.bndcnd == 5:
            return 3  # periodic +
        if node.bndcnd == 8 or node.bndcnd == 9:
            return 1  # vpot 0

    def physical_surface(e):

        def surface_id(name):
            return physical_surfaces.index(name) + len(physical_lines) + 1

        if any(e.mag):
            if e.mag[0] > 0:
                if e.mag[1] > 0:
                    return surface_id("PM1")
                return surface_id("PM2")
            if e.mag[1] > 0:
                return surface_id("PM3")
            return surface_id("PM4")

        if e in airgap_rotor_elements or e in airgap_center_elements:
            return surface_id("Airgap_Rotor")

        if e in airgap_stator_elements:
            return surface_id("Airgap_Stator")

        sr_key = isa.superelements[e.se_key].sr_key
        if sr_key == -1:
            v = e.vertices[0]
            if np.sqrt(v.x**2 + v.y**2) > isa.FC_RADIUS:
                return surface_id("Air_Stator")
            return surface_id("Air_Rotor")

        sr = isa.subregions[sr_key]
        if sr.wb_key != -1:
            wb = isa.subregions[sr.wb_key]
            if sr.curdir > 0:
                return surface_id("Winding_{}_-".format(wb.key))
            return surface_id("Winding_{}_+".format(wb.key))

        return surface_id(sr.name)

    def line_on_boundary(n1, n2):
        if n1.on_boundary() and n2.on_boundary():
            if n1 in nodechain_links.keys():
                return n2 in nodechain_links[n1]
            else:
                return False
        else:
            return (n1, n2) in airgap_lines or (n2, n1) in airgap_lines

    def induction(e):
        if e.el_type == 1:
            y31 = ev[2].y - ev[0].y
            y21 = ev[1].y - ev[0].y
            x13 = ev[0].x - ev[2].x
            x21 = ev[1].x - ev[0].x
            a21 = ev[1].vpot[0] - ev[0].vpot[0]
            a31 = ev[2].vpot[0] - ev[0].vpot[0]
            #a23 = ev[2].vpot[0] - ev[1].vpot[0]
            length = isa.superelements[e.se_key].length
            delta = length * (y31 * x21 + y21 * x13)
            
            b1 = (x13 * a21 + x21 * a31) / delta
            b2 = (-y31 * a21 + y21 * a31) / delta
            
        elif e.el_type == 2:
            y31 = ev[2].y - ev[0].y
            y21 = ev[1].y - ev[0].y
            x13 = ev[0].x - ev[2].x
            x21 = ev[1].x - ev[0].x
            a21 = ev[1].vpot[0] - ev[0].vpot[0]
            a31 = ev[2].vpot[0] - ev[0].vpot[0]
            length = isa.superelements[e.se_key].length
            delta = length * (y31 * x21 + y21 * x13)
            b1_a = (x13 * a21 + x21 * a31) / delta
            b2_a = (y21 * a31 - y31 * a21) / delta

            y31 = ev[0].y - ev[2].y
            y21 = ev[3].y - ev[2].y
            x13 = ev[2].x - ev[0].x
            x21 = ev[3].x - ev[2].x
            a24 = ev[3].vpot[0] - ev[2].vpot[0]
            a34 = ev[0].vpot[0] - ev[2].vpot[0]
            #a41 = ev[3].vpot[0] - ev[0].vpot[0] 
            delta = length * (y31 * x21 + y21 * x13)
            b1_b = (x13 * a24 + x21 * a34) / delta
            b2_b = (y21 * a34 - y31 * a24) / delta

            b1 = (b1_a + b1_b) / 2
            b2 = (b2_a + b2_b) / 2
            
        return b1, b2

    def demagnetization(e):
        if abs(e.mag[0]) > 1e-5 or abs(e.mag[1]) > 1e-5:
            magn = np.sqrt(e.mag[0]**2 + e.mag[1]**2)
            alfa = np.arctan2(e.mag[1], e.mag[0])
            b1, b2 = induction(e)
            bpol = b1 * np.cos(alfa) + b2 * np.sin(alfa)
            hpol = bpol - magn
            if hpol < 0:
                reluc = 795774.7 * abs(e.reluc[0]) / 1000
                return abs(hpol * reluc)
        return 0

    def permeability(e):
        if e.reluc[0] < 1:
            return 1 / e.reluc[0]
        return 0

    def losses(e):
        return isa.ELEM_ISA_ELEM_REC_LOSS_DENS[e.key-1] * 1e-6

    points = [[n.x, n.y, 0] for n in isa.nodes]
    vpot = [n.vpot[0] for n in isa.nodes]

    lines = []
    line_ids = []
    triangles = []
    triangle_physical_ids = []
    triangle_geometrical_ids = []
    triangle_b = []
    triangle_h = []
    triangle_perm = []
    triangle_losses = []
    quads = []
    quad_physical_ids = []
    quad_geometrical_ids = []
    quad_b = []
    quad_h = []
    quad_perm = []
    quad_losses = []
    for e in isa.elements:
        ev = e.vertices
        for i, v in enumerate(ev):
            v1, v2 = v, ev[i-1]
            if line_on_boundary(v1, v2):
                lines.append([v1.key - 1, v2.key - 1])
                line_ids.append(physical_line(v1, v2))

        if len(ev) == 3:
            triangles.append([n.key - 1 for n in ev])
            triangle_physical_ids.append(physical_surface(e))
            triangle_geometrical_ids.append(e.key)
            triangle_b.append(induction(e))
            triangle_h.append(demagnetization(e))
            triangle_perm.append(permeability(e))
            triangle_losses.append(losses(e))

        elif len(ev) == 4:
            quads.append([n.key - 1 for n in ev])
            quad_physical_ids.append(physical_surface(e))
            quad_geometrical_ids.append(e.key)
            quad_b.append(induction(e))
            quad_h.append(demagnetization(e))
            quad_perm.append(permeability(e))
            quad_losses.append(losses(e))


    if target_format == "msh":
        points = np.array(points)

        cells = {"line": np.array(lines),
                 "triangle": np.array(triangles),
                 "quad": np.array(quads)}

        point_data = {"potential": np.array(vpot)}

        cell_data = {
            "line": {
                "gmsh:geometrical": np.array(line_ids),
                "gmsh:physical": np.array(line_ids),
                "b": np.array([(0, 0, 0) for l in lines]),
                "h": np.array([0 for l in lines]),
                "Rel. Permeability": np.array([0 for l in lines]),
                "Losses": np.array([0 for l in lines]),
            },
            "triangle": {
                "gmsh:geometrical": np.array(triangle_geometrical_ids),
                "gmsh:physical": np.array(triangle_physical_ids),
                "b": np.array([b + (0,) for b in triangle_b]),
                "h": np.array(triangle_h),
                "Rel. Permeability": np.array(triangle_perm),
                "Losses": np.array(triangle_losses),
            },
            "quad": {
                "gmsh:geometrical": np.array(quad_geometrical_ids),
                "gmsh:physical": np.array(quad_physical_ids),
                "b": np.array([b + (0,) for b in quad_b]),
                "h": np.array(quad_h),
                "Rel. Permeability": np.array(quad_perm),
                "Losses": np.array(quad_losses),
            }
        }

        field_data = {}
        for l in physical_lines:
            field_data[l] = np.array([physical_lines.index(l) + 1, 1])
        for s in physical_surfaces:
            field_data[s] = np.array([physical_surfaces.index(s) + 1
                                      + len(physical_lines), 2])
        meshio.write_points_cells(filename,
                                  points,
                                  cells,
                                  point_data,
                                  cell_data,
                                  field_data,
                                  "gmsh-ascii")


    if target_format == "geo":
        geo = []
        nc_nodes = set([n for nc in isa.nodechains for n in nc.nodes])

        for n in isa.nodes:
            if n in nc_nodes:
                geo.append("Point({}) = {{{}, {}, {}}};".format(
                    n.key, n.x, n.y, 0))

        for nc in isa.nodechains:
            geo.append("Line({}) = {{{}}};".format(
                    nc.key, ", ".join([str(n.key) for n in nc.nodes])))
        used = set()
        for nc in isa.nodechains:
            n1, n2 = nc.nodes[0], nc.nodes[1]
            if line_on_boundary(n1, n2):
                id_ = physical_line(n1, n2)
                name = physical_lines[id_ - 1]
                if extrude:
                    geo.append(
                        "extrusion[] = Extrude {{0, 0, {}}} {{ Line{{{}}}; {}{}}};".format(
                            extrude,
                            nc.key,
                            "Layers{{{}}}; ".format(layers) if layers else "",
                            "Recombine; " if recombine else ""))

                    geo.append("Physical Surface('{}', {}) {} extrusion[1];".format(
                        name,
                        id_,
                        "+=" if name in used else "="))
                else:
                    geo.append("Physical Line('{}', {}) {} {{{}}};".format(
                        name,
                        id_,
                        "+=" if name in used else "=",
                        nc.key))
                used.add(name)

        for se in isa.superelements:
            geo.append("Line Loop({}) = {{{}}};".format(
                se.key,
                ", ".join([str(nc.key) for nc in se.nodechains])))
            geo.append("Plane Surface({0}) = {{{0}}};".format(se.key))
        used = set()
        for se in isa.superelements:
            id_ = physical_surface(se.elements[0]) - len(physical_lines)
            name = physical_surfaces[id_ - 1]
            if extrude:
                geo.append(
                    "extrusion[] = Extrude {{0, 0, {}}} {{ Surface{{{}}}; {}{}}};".format(
                        extrude,
                        se.key,
                        "Layers{{{}}}; ".format(layers) if layers else "",
                        "Recombine; " if recombine else ""))

                geo.append("Physical Surface('base', {}) {} {{{}}};".format(
                    len(physical_lines) + 1,
                    "=" if se.key == 1 else "+=",
                    se.key))

                geo.append("Physical Surface('top', {}) {} extrusion[0];".format(
                    len(physical_lines) + 2,
                    "=" if se.key == 1 else "+="))

                geo.append("Physical Volume('{}', {}) {} extrusion[1];".format(
                    name,
                    id_,
                    "+=" if name in used else "="))
            else:
                geo.append("Physical Surface('{}', {}) {} {{{}}};".format(
                    name,
                    id_,
                    "+=" if name in used else "=",
                    se.key))
            used.add(name)
        
        with open(filename, "w") as f:
            f.write("\n".join(geo))

    if target_format == "vtu":

        assert len(points) == len(vpot)
        assert len(lines) == len(line_ids)
        assert len(triangles) == len(triangle_physical_ids) == len(triangle_geometrical_ids) == len(triangle_b) == len(triangle_h) == len(triangle_perm)
        assert len(quads) == len(quad_physical_ids) == len(quad_geometrical_ids) == len(quad_b) == len(quad_h) == len(quad_perm)

        points = np.array(points)

        cells = {"line": np.array(lines),
                 "triangle": np.array(triangles),
                 "quad": np.array(quads)}

        point_data = {"potential": np.array(vpot)}

        cell_data = {
            "line": {
                "GeometryIds": np.array(line_ids),
                "PhysicalIds": np.array(line_ids),
                "b": np.array([(0, 0) for l in lines]),
                "Demagnetization": np.array([0 for l in lines]),
                "Rel. Permeability": np.array([0 for l in lines]),
                "Losses": np.array([0 for l in lines]),
            },
            "triangle": {
                "GeometryIds": np.array(triangle_geometrical_ids),
                "PhysicalIds": np.array(triangle_physical_ids),
                "b": np.array(triangle_b),
                "Demagnetization": np.array(triangle_h),
                "Rel. Permeability": np.array(triangle_perm),
                "Losses": np.array(triangle_losses),
            },
            "quad": {
                "GeometryIds": np.array(quad_geometrical_ids),
                "PhysicalIds": np.array(quad_physical_ids),
                "b": np.array(quad_b),
                "Demagnetization": np.array(quad_h),
                "Rel. Permeability": np.array(quad_perm),
                "Losses": np.array(quad_losses),
            }
        }

        field_data = {}
        for l in physical_lines:
            field_data[l] = np.array([physical_lines.index(l) + 1, 1])
        for s in physical_surfaces:
            field_data[s] = np.array([physical_surfaces.index(s) + 1
                                      + len(physical_lines), 2])
        meshio.write_points_cells(filename,
                                  points,
                                  cells,
                                  point_data=point_data,
                                  cell_data=cell_data,
                                  field_data=field_data,
                                  file_format="vtu-binary")


def to_msh(source, filename, infile_type=None):
    """
    Convert a femag model to msh format.

    Arguments:
        source: instance of femagtools.isa7.Isa7 or name of I7/ISA7 file
        filename: name of converted file
        infile_type: format of source file
    """
    if isinstance(source, isa7.Isa7):
        _from_isa(source, filename, "msh")

    elif type(source) == str:
        if infile_type:
            file_ext = infile_type.lower()
        else:
            file_ext = source.split(".")[-1].lower()

        if file_ext in ["isa7", "a7"]:
            isa = isa7.read(source)
            _from_isa(isa, filename, "msh")
        else:
            raise ValueError(
                "cannot convert files of format {} to .msh".format(file_ext))
    else:
        raise ValueError("cannot convert {} to .msh".format(source))

    
def to_geo(source, filename, extrude=0, layers=0,
           recombine=False, infile_type=None):
    """
    Convert a femag model to geo format.

    Arguments:
        source: instance of isa7.Isa7 or name of an I7/ISA7 file
        filename: name of converted file
        extrude: extrude surfaces using a translation along the z-axis
        layers: number of layers to create when extruding
        recombine: when extruding, recombine triangles into quadrangles and tetraedra into to prisms, hexahedra or pyramids
        infile_type: format of source file
    """
    if isinstance(source, isa7.Isa7):
        _from_isa(source, filename, "geo", extrude, layers, recombine)
        
    elif type(source) == str:
        if infile_type:
            file_ext = infile_type.lower()
        else:
            file_ext = source.split(".")[-1].lower()
        
        if file_ext in ["isa7", "a7"]:
            isa = isa7.read(source)
            _from_isa(isa, filename, "geo", extrude, layers, recombine)
        else:
            raise ValueError(
                "cannot convert files of format {} to .geo".format(file_ext))
    else:
        raise ValueError("cannot convert {} to .geo".format(source))


def to_vtu(source, filename, infile_type=None):
    """
    Convert a femag model to vtu format.

    Arguments:
        source: instance of isa7.Isa7 or name of an I7/ISA7 file
        filename: name of converted file
        infile_type: format of source file
    """
    if isinstance(source, isa7.Isa7):
        _from_isa(source, filename, "vtu")

    elif type(source) == str:
        if infile_type:
            file_ext = infile_type.lower()
        else:
            file_ext = source.split(".")[-1].lower()

        if file_ext in ["isa7", "a7"]:
            isa = isa7.read(source)
            _from_isa(isa, filename, "vtu")
        else:
            raise ValueError(
                "cannot convert files of format {} to .vtu".format(file_ext))
    else:
        raise ValueError("cannot convert {} to .vtu".format(source))
