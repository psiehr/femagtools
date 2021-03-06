# -*- coding: utf-8 -*-
"""
    NOTE: This code is in highly experimental state.
          Use at your own risk.

  Author: Ronald Tanner
    Date: 2017/07/06
"""
from __future__ import print_function
import numpy as np
import logging
from .functions import less_equal
from .functions import distance, line_m, line_n
from .functions import point, points_are_close, points_on_arc
from .functions import alpha_line, alpha_angle, alpha_triangle
from .functions import normalise_angle, min_angle, get_angle_of_arc
from .functions import lines_intersect_point
from .functions import is_angle_inside
# from .geom import ndec

logger = logging.getLogger('femagtools.geom')


#############################
#       Shape (Basis)       #
#############################

class Element(object):
    """value object class"""
    def __init__(self, **kwargs):
        for k in kwargs.keys():
            setattr(self, k, kwargs[k])


#############################
#       Shape (Basis)       #
#############################

class Shape(object):
    """an abstract geometry with 2 points"""
    def start(self):
        return self.p1

    def end(self):
        return self.p2

    def node1(self, ndec):
        return round(self.p1[0], ndec), round(self.p1[1], ndec)

    def node2(self, ndec):
        return round(self.p2[0], ndec), round(self.p2[1], ndec)

    def xmin(self):
        return min(self.p1[0], self.p2[0])

    def xmax(self):
        return max(self.p1[0], self.p2[0])

    def ymin(self):
        return min(self.p1[1], self.p2[1])

    def ymax(self):
        return max(self.p1[1], self.p2[1])

    def dx(self):
        return (self.p2[0]-self.p1[0])

    def dy(self):
        return (self.p2[1]-self.p1[1])

    def m(self, none_val=None):
        m = line_m(self.p1, self.p2)
        if m is None:
            return none_val
        else:
            return m

    def n(self, m):
        return line_n(self.p1, m)

    def move(self, dist):
        self.p1 = self.p1[0] + dist[0], self.p1[1] + dist[1]
        self.p2 = self.p2[0] + dist[0], self.p2[1] + dist[1]

    def scale(self, factor):
        self.p1 = factor*self.p1[0], factor*self.p1[1]
        self.p2 = factor*self.p2[0], factor*self.p2[1]

    def transform(self, T, **kwargs):
        n = T.dot(np.array((self.p1[0], self.p1[1])))
        self.p1 = (n[0], n[1])
        n = T.dot(np.array((self.p2[0], self.p2[1])))
        self.p2 = (n[0], n[1])
        return self

    def intersect_shape(self, e, rtol=1e-03, atol=1e-03, include_end=False):
        if isinstance(e, Line):
            return self.intersect_line(e, rtol, atol, include_end)
        if isinstance(e, Arc):
            return self.intersect_arc(e, rtol, atol, include_end)
        if isinstance(e, Circle):
            return self.intersect_circle(e, rtol, atol, include_end)
        return []

    def get_point_number(self, p):
        if points_are_close(p, self.p1, rtol=0.0, atol=0.001) and \
           points_are_close(p, self.p2, rtol=0.0, atol=0.001):
            logger.debug("WARNING: get_point_number(): " +
                         "both points are close !!")
        if points_are_close(p, self.p1, rtol=0.0, atol=0.001):
            return 1
        if points_are_close(p, self.p2, rtol=0.0, atol=0.001):
            return 2
        return 0

    def minmax_angle_dist_from_center(self, center, dist):
        dist_p1 = distance(center, self.p1)
        dist_p2 = distance(center, self.p2)
        if np.isclose(dist, dist_p1):
            alpha_p1 = alpha_line(center, self.p1)
            if np.isclose(dist, dist_p2):
                alpha_p2 = alpha_line(center, self.p2)
                if alpha_angle(alpha_p1, alpha_p2) < np.pi:
                    return (alpha_p1, alpha_p2)
                else:
                    return (alpha_p2, alpha_p1)
            else:
                return (alpha_p1, alpha_p1)
        else:
            if np.isclose(dist, dist_p2):
                alpha_p2 = alpha_line(center, self.p2)
                return (alpha_p2, alpha_p2)
        return ()

    def __str__(self):
        return " {}/{}".format(self.p1, self.p2)

    def __lt__(self, s):
        return False


#############################
#       Circle (Shape)      #
#############################

class Circle(Shape):
    """a circle with center and radius"""
    def __init__(self, e):
        self.center = e.center[:2]
        self.radius = e.radius
        self.p1 = self.center[0]-self.radius, self.center[1]
        self.p2 = self.center[0]+self.radius, self.center[1]

    def render(self, renderer, color='blue', with_nodes=False):
        renderer.circle(self.center, self.radius, color)
        if with_nodes:
            renderer.point(self.center, 'ro', 'white')

    def move(self, dist):
        super(Circle, self).move(dist)
        self.center = self.center[0]+dist[0], self.center[1]+dist[1]

    def minmax(self):
        """ Die Funktion bestimmt das Minimum und Maximum auf der x- und der
            y-Achse (return [<min-x>, <max-x>, <min-y>, <max-y>])
        """
        return [self.center[0]-self.radius, self.center[0]+self.radius,
                self.center[1]-self.radius, self.center[1]+self.radius]

    def minmax_from_center(self, center):
        """ Die Funktion ermittelt den minimalen und maximalen Abstand vom Center
        """
        d = distance(center, self.center)
        if np.isclose(d, 0.0):
            return (self.radius, self.radius)

        dist_min = abs(d - self.radius)
        dist_max = d + self.radius
        return (dist_min, dist_max)

    def minmax_angle_from_center(self, center):
        d = distance(center, self.center)
        r = self.radius
        if r >= d:
            return (0.0, 0.0)

        r2 = np.sqrt(d**2 - r**2)
        circ = Circle(Element(center=center, radius=r2))
        points = self.intersect_circle(circ)

        if len(points) == 2:
            alpha_p1 = alpha_line(center, points[0])
            alpha_p2 = alpha_line(center, points[1])
            if alpha_angle(alpha_p1, alpha_p2) < np.pi:
                return (alpha_p1, alpha_p2)
            else:
                return (alpha_p2, alpha_p1)
        else:
            return (0.0, 0.0)

    def minmax_angle_dist_from_center(self, center, dist):
        return ()

    def get_nodes(self, parts=8):
        """ returns a list of virtual nodes to create the convex hull
        """
        return (p for p in points_on_arc(self.center, self.radius,
                                         0.0,  # startangle
                                         0.0,  # endangle
                                         parts=parts))

    def scale(self, factor):
        super(Circle, self).scale(factor)
        self.center = factor*self.center[0], factor*self.center[1]
        self.radius = factor*self.radius

    def transform(self, T, **kwargs):
        super(Circle, self).transform(T)
        n = T.dot(np.array((self.center[0], self.center[1])))
        self.center = (n[0], n[1])
        return self

    def center_of_connection(self, ndec):
        return (self.center[0] + self.radius, self.center[1])

    def intersect_line(self, line, rtol=1e-03, atol=1e-03, include_end=False):
        """ Von einem Circle-Objekt und einem Line-Objekt werden die
            Schnittpunkte bestimmt und in einer Liste ausgegeben.
        """
        line_m = line.m()
        p = []
        if line_m is None:
            p = [line.p1[0], self.center[1]]
        elif np.isclose(line_m, 0.0, rtol, atol):
            p = [self.center[0], line.p1[1]]
        else:
            m = -1/line_m
            p = lines_intersect_point(line.p1, line_m, line.n(line_m),
                                      self.center, m, line_n(self.center, m))

        d = distance(self.center, p)

        if np.isclose(d, self.radius, rtol, atol):
            if line.is_point_inside(p, rtol, atol, include_end):
                # Wenn der Abstand d dem Radius entspricht, handelt es sich um
                # eine Tangente und es gibt genau einen Schnittpunkt
                if include_end:
                    return [p]
                else:
                    return []
        if self.radius < d:
            # d liegt ausserhalb des Kreises -> kein Schnittpunkt
            return []

        A = np.sqrt(self.radius**2 - d**2)
        delta = alpha_line(line.p1, line.p2)

        p1 = point(p, -A, delta)
        p2 = point(p, A, delta)

        # Die Schnittpunkte p1 und p2 sind bestimmt. Nun muss noch sicher
        # gestellt werden, dass sie innerhalb des Start- und Endpunkts der
        # Linie liegen
        p1_inside = line.is_point_inside(p1, rtol, atol, include_end)
        p2_inside = line.is_point_inside(p2, rtol, atol, include_end)
        if p1_inside:
            if p2_inside:
                return [p1, p2]
            else:
                return[p1]
        else:
            if p2_inside:
                return[p2]
            else:
                return []

    def intersect_circle(self, circle, rtol=1e-03, atol=1e-03,
                         include_end=False):
        """ Von zwei Circle-Objekten werden die Schnittpunkte bestimmt
            und in einer Liste ausgegeben
        """
        d = distance(self.center, circle.center)
        arc = alpha_triangle(circle.radius, self.radius, d)

        if np.isnan(arc):
            if not np.isclose(d, circle.radius + self.radius,
                              rtol, atol):
                return []
            arc = 0.0
        arc_C = alpha_line(self.center, circle.center)
        p1 = point(self.center, self.radius, arc_C+arc)
        p2 = point(self.center, self.radius, arc_C-arc)
        if points_are_close(p1, p2, rtol, atol):
            # Tangente
            if include_end:
                return [p1]
            else:
                return []
        return [p1, p2]

    def intersect_arc(self, arc, rtol=1e-03, atol=1e-03, include_end=False):
        """ Von einem Circle-Objekt und einem Arc-Objekt werden die
            Schnittpunkte bestimmt und in einer Liste ausgegeben
        """
        assert(isinstance(arc, Arc))
        # let Arc do the work
        return arc.intersect_circle(self, rtol, atol, include_end)

    def split(self, points, rtol, atol):
        """ Die Funktion splittet das Circle-Objekt an den vorgegebenen Punkten
            und gibt eine Liste der neu enstandenen Elemente aus.
        """
        if len(points) == 1:
            p = points[0]
            split_arcs = []
            alpha1 = alpha_line(self.center, p)
            alpha2 = normalise_angle(alpha1 + np.pi/2)
            alpha3 = normalise_angle(alpha1 + np.pi)

            arc = Arc(Element(center=self.center, radius=self.radius,
                              start_angle=alpha1*180/np.pi,
                              end_angle=alpha2*180/np.pi))
            split_arcs.append(arc)

            arc = Arc(Element(center=self.center, radius=self.radius,
                              start_angle=alpha2*180/np.pi,
                              end_angle=alpha3*180/np.pi))
            split_arcs.append(arc)

            arc = Arc(Element(center=self.center, radius=self.radius,
                              start_angle=alpha3*180/np.pi,
                              end_angle=alpha1*180/np.pi))
            split_arcs.append(arc)
            return split_arcs

        assert(len(points) == 0)
        return []

    def get_angle_of_arc(self):
        return np.pi*2.0

    def __str__(self):
        return "Circle c={}, r={}".format(self.center, self.radius)

    def __eq__(self, other):
        """Override the default Equals behavior"""
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        """Define a non-equality test"""
        return not self == other

    def __hash__(self):
        """ Override the default hash behavior
            (that returns the id or the object)
        """
        return hash(tuple(sorted(self.__dict__.items())))


#############################
#        Arc (Shape)        #
#############################

class Arc(Circle):
    """a counter clockwise segment of a circle with start and end point"""
    def __init__(self, e):
        super(self.__class__, self).__init__(e)
        self.startangle = e.start_angle/180*np.pi
        self.endangle = e.end_angle/180*np.pi
        if self.endangle < self.startangle:
            if self.endangle < 0:
                self.endangle += 2*np.pi
            elif self.startangle < 0:
                self.startangle += 2*np.pi
            else:
                self.endangle -= 2*np.pi

        self.p1 = (self.center[0] + e.radius*np.cos(self.startangle),
                   self.center[1] + e.radius*np.sin(self.startangle))
        self.p2 = (self.center[0] + e.radius*np.cos(self.endangle),
                   self.center[1] + e.radius*np.sin(self.endangle))

    def render(self, renderer, color='blue', with_nodes=False):
        renderer.arc(self.startangle, self.endangle,
                     self.center, self.radius, color)
        if with_nodes:
            renderer.point(self.p1, 'ro', color)
            renderer.point(self.p2, 'ro', color)

    def center_of_connection(self, ndec):
        s = self.startangle
        d = self.endangle - s
        if d > 2*np.pi:
            d -= 2*np.pi
        x, y = self(s + d/2)
        return (round(x, ndec), round(y, ndec))

    def length(self):
        """returns length of this arc"""
        d = abs(self.endangle - self.startangle)
        if d > 2*np.pi:
            d -= 2*np.pi
        return self.radius*abs(d)

    def range(self, step=1.0):
        """returns evenly spaced values"""
        num = max(self.length()/step, 1)
        astep = self.length()/num/self.radius
        s = self.startangle
        d = self.endangle - s
        if d > 2*np.pi:
            d -= 2*np.pi
        alpha = np.arange(s, s+d, astep)
        return self(alpha)

    def __call__(self, alpha):
        """returns x,y coordinates of angle"""
        return (self.center[0] + self.radius*np.cos(alpha),
                self.center[1] + self.radius*np.sin(alpha))

    def intersect_line(self, line, rtol=1e-03, atol=1e-03, include_end=False):
        """ Von einem Arc-Objekt und einem Line-Objekt werden die
            Schnittpunkte bestimmt und in einer Liste ausgegeben
        """
        points = super(Arc, self).intersect_line(line, rtol, atol, include_end)

        # all possible points have been found
        # Lets see if they are on a arc
        remaining_points = []
        for p in points:
            if self.is_point_inside(p, rtol, atol, include_end):
                remaining_points.append(p)
        return remaining_points

    def intersect_arc(self, arc, rtol=1e-03, atol=1e-03, include_end=False):
        """ Von zwei Arc-Objekten werden die Schnittpunkte bestimmt und in
            einer Liste ausgegeben.
        """
        assert(isinstance(arc, Arc))
        points = self.intersect_circle(arc, rtol, atol, include_end)

        # Check if the points are on a arc
        # (has been assumed as a circle)
        remaining_points = []
        for p in points:
            if arc.is_point_inside(p, rtol, atol, include_end):
                remaining_points.append(p)
        return remaining_points

    def intersect_circle(self, circle, rtol=1e-03,
                         atol=1e-03, include_end=False):
        """ return the list of intersection points
        """
        if points_are_close(self.center, circle.center, rtol, atol):
            if np.isclose(self.radius, circle.radius):
                if include_end:
                    return [self.p1, self.p2]
            # no intersection with different radius but equal center
            return []

        points = super(Arc, self).intersect_circle(
            circle, rtol, atol, include_end)

        # Intersection points exist. Take the ones on the arc
        remaining_points = []
        for p in points:
            if self.is_point_inside(p, rtol, atol, include_end):
                remaining_points.append(p)
        return remaining_points

    def split(self, points, rtol=1e-03, atol=1e-03):
        """ return a list of arcs by splitting
        """
        points_inside = [p
                         for p in points
                         if self.is_point_inside(p, rtol, atol, False)]
        if len(points_inside) == 1:
            p = points_inside[0]
            split_arcs = []
            alpha = alpha_line(self.center, p)
            arc = Arc(Element(center=self.center, radius=self.radius,
                              start_angle=self.startangle*180/np.pi,
                              end_angle=alpha*180/np.pi))
            split_arcs.append(arc)

            arc = Arc(Element(center=self.center, radius=self.radius,
                              start_angle=alpha*180/np.pi,
                              end_angle=self.endangle*180/np.pi))
            split_arcs.append(arc)
            return split_arcs

        assert(len(points_inside) == 0)
        return []

    def is_point_inside(self, p, rtol=1e-03, atol=1e-03, include_end=False):
        """ returns true if p is on arc
        """
        if points_are_close(p, self.p1, rtol, atol):
            return include_end
        elif points_are_close(p, self.p2, rtol, atol):
            return include_end
        elif points_are_close(self.p1, self.p2, rtol, atol):
            return False

        alpha_p1 = alpha_line(self.center, self.p1)
        alpha_p2 = alpha_line(self.center, self.p2)
        alpha_p = alpha_line(self.center, p)
        alpha_inside = is_angle_inside(alpha_p1, alpha_p2, alpha_p)
        return alpha_inside

    def is_angle_inside(self, alpha, rtol=1e-03, atol=1e-03,
                        include_end=False):
        """ returns True if alpha is between start and end angle
        """
        return is_angle_inside(self.startangle, self.endangle, alpha)

    def transform(self, T, **kwargs):
        super(Arc, self).transform(T)
        p1, p2 = ((self.p1[0]-self.center[0],
                   self.p1[1]-self.center[1]),
                  (self.p2[0]-self.center[0],
                   self.p2[1]-self.center[1]))

        if kwargs.get('reflect', False):
            self.p1, self.p2 = self.p2, self.p1
            self.endangle = np.arctan2(p1[1], p1[0])
            self.startangle = np.arctan2(p2[1], p2[0])
        else:
            self.startangle = np.arctan2(p1[1], p1[0])
            self.endangle = np.arctan2(p2[1], p2[0])
        return self

    def minmax(self):
        """ Die Funktion bestimmt das Minimum und Maximum auf der x- und der
            y-Achse (return [<min-x>, <max-x>, <min-y>, <max-y>])
        """
        mm = [min(self.p1[0], self.p2[0]), max(self.p1[0], self.p2[0]),
              min(self.p1[1], self.p2[1]), max(self.p1[1], self.p2[1])]

        p = [self.center[0]-self.radius, self.center[1]]
        if p[0] < mm[0]:
            a = alpha_line(self.center, p)
            if self.is_angle_inside(a, 0.00001):
                mm[0] = p[0]

        p = [self.center[0]+self.radius, self.center[1]]
        if p[0] > mm[1]:
            a = alpha_line(self.center, p)
            if self.is_angle_inside(a, 0.00001):
                mm[1] = p[0]

        p = [self.center[0], self.center[1]-self.radius]
        if p[1] < mm[2]:
            a = alpha_line(self.center, p)
            if self.is_angle_inside(a, 0.00001):
                mm[2] = p[1]

        p = [self.center[0], self.center[1]+self.radius]
        if p[1] > mm[3]:
            a = alpha_line(self.center, p)
            if self.is_angle_inside(a, 0.00001):
                mm[3] = p[1]
        return mm

    def minmax_from_center(self, center):
        """ Die Funktion ermittelt den minimalen und maximalen
            Abstand vom Center
        """
        d = distance(center, self.center)
        if np.isclose(d, 0.0):
            return (self.radius, self.radius)

        angle = alpha_line(center, self.center)
        dist_min = abs(d - self.radius)
        dist_max = d + self.radius

        pmax = point(center, d + self.radius, angle)
        alpha_pmax = alpha_line(self.center, pmax)
        if not self.is_angle_inside(alpha_pmax, 1e-08):
            dist_max = max(distance(center, self.p1),
                           distance(center, self.p2))

        pmin = point(center, d - self.radius, angle)
        alpha_pmin = alpha_line(self.center, pmin)

        if not self.is_angle_inside(alpha_pmin, 1e-08):
            dist_min = min(distance(center, self.p1),
                           distance(center, self.p2))

        return (dist_min, dist_max)

    def minmax_angle_from_center(self, center):
        d = distance(center, self.center)
        r = self.radius
        v = d**2 - r**2
        if less_equal(v, 0.0):
            points = []
        else:
            r2 = np.sqrt(v)
            circ = Circle(Element(center=center, radius=r2))
            points = self.intersect_circle(circ)

        points.append(self.p2)

        alpha_min = alpha_line(center, self.p1)
        alpha_max = alpha_min

        for p in points:
            alpha_p = alpha_line(center, p)
            alpha_min = min_angle(alpha_min, alpha_p)
            alpha_max = min_angle(alpha_max, alpha_p)

        return (alpha_min, alpha_max)

    def get_nodes(self, parts=8):
        """ Die Funktion liefert eine Liste von virtuellen Nodes, welche man
            zum Rechnen der convex_hull() benötigt.
        """
        return (p for p in points_on_arc(self.center, self.radius,
                                         self.startangle,
                                         self.endangle,
                                         parts=parts))

    def get_angle_of_arc(self):
        return get_angle_of_arc(self.startangle, self.endangle)

    def __str__(self):
        return "Arc c={}, r={} start={}, end={}, p1={}, p2={}".\
            format(self.center,
                   self.radius, self.startangle,
                   self.endangle,
                   self.p1,
                   self.p2)

    def __eq__(self, other):
        """Override the default Equals behavior"""
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        """Define a non-equality test"""
        return not self == other

    def __hash__(self):
        """ Override the default hash behavior
            (that returns the id or the object)
        """
        return hash(tuple(sorted(self.__dict__.items())))


#############################
#        Line (Shape)       #
#############################

class Line(Shape):
    """straight connection between start and end point"""
    def __init__(self, e):
        self.p1 = e.start[0], e.start[1]
        self.p2 = e.end[0], e.end[1]

    def render(self, renderer, color='blue', with_nodes=False):
        renderer.line(self.p1, self.p2, color)
        if with_nodes:
            renderer.point(self.p1, 'ro', color)
            renderer.point(self.p2, 'ro', color)

    def center_of_connection(self, ndec):
        x = (self.p1[0]+self.p2[0])/2
        y = (self.p1[1]+self.p2[1])/2
        return (x, y)

    def length(self):
        return np.sqrt(self.dx()**2 + self.dy()**2)

    def range(self, step=1.0):
        """returns evenly spaced values"""
        num = max(int(self.length()/step), 1)
        if np.isclose(self.dx(), 0):
            if np.isclose(self.dy(), 0):
                return ((self.xmin(),), (self.ymin(),))
            y = np.arange(self.ymin(), self.ymax(), self.length()/num)
            return np.array((self.xmin()*np.ones(len(y)), y))
        xstep = np.sqrt((self.length()/num)**2/(1 + self.dy()**2/self.dx()**2))
        x = np.arange(self.xmin(), self.xmax(), xstep)
        return (x, self(x))

    def __call__(self, x):
        """returns y coordinate of x"""
        if np.isclose(self.dx(), 0):
            return float('nan')
        return self.dy()/self.dx()*(x - self.p1[0]) + self.p1[1]

    def intersect_line(self, line, rtol=1e-03, atol=1e-03, include_end=False):
        """ Von zwei Line-Objekten wird der Schnittpunkt bestimmt und in
            einer Liste ausgegeben.
        """
        point = []
        m_L1 = self.m()
        m_L2 = line.m()
        if m_L1 is None:
            if m_L2 is None:
                return []
            else:
                y = line_n([line.p1[0]-self.p1[0], line.p1[1]], m_L2)
                point = (self.p1[0], y)
        else:
            if m_L2 is None:
                y = line_n([self.p1[0]-line.p1[0], self.p1[1]], m_L1)
                point = (line.p1[0], y)
            else:
                if np.isclose(m_L1, m_L2):
                    return []
                else:
                    point = lines_intersect_point(self.p1, m_L1, self.n(m_L1),
                                                  line.p1, m_L2, line.n(m_L2))

        if line.is_point_inside(point, rtol, atol, include_end):
            if self.is_point_inside(point, rtol, atol, include_end):
                return [point]
        return []

    def intersect_arc(self, arc, rtol=1e-03, atol=1e-03, include_end=False):
        """ Von einem Line-Objekt und einem Arc-Objekt werden die
            Schnittpunkte bestimmt und in einer Liste ausgegeben.
        """
        return arc.intersect_line(self, rtol, atol, include_end)

    def intersect_circle(self, circle, rtol=1e-03, atol=1e-03,
                         include_end=False):
        """ Von einem Line-Objekt und einem Circle-Objekt werden die
            Schnittpunkte bestimmt und in einer Liste ausgegeben.
        """
        return circle.intersect_line(self, rtol, atol, include_end)

    def split(self, points, rtol=1e-03, atol=1e-03):
        """ Die Funktion splittet das Line-Objekt an den vorgegebenen Punkten
            und gibt eine Liste der neu enstandenen Elemente aus.
        """
        points_inside = [(distance(p, self.p1), p)
                         for p in points if self.is_point_inside(p,
                                                                 rtol, atol,
                                                                 False)]

        if len(points_inside) > 0:
            points_inside.append((0.0, self.p1))
            points_inside.append((distance(self.p1, self.p2), self.p2))
            points_inside.sort()

            split_lines = []
            p_start = None
            for d, p in points_inside:
                if p_start is not None:
                    split_lines.append(Line(Element(start=p_start, end=p)))

                p_start = p
            return split_lines
        return []

    def is_point_inside(self, point, rtol, atol, include_end=False):
        """ returns True if point is between start and end point
        """
        if points_are_close(point, self.p1, rtol, atol):
            return include_end
        if points_are_close(point, self.p2, rtol, atol):
            return include_end

        m1 = line_m(self.p1, point)
        m2 = line_m(point, self.p2)
        if m1 is None or m2 is None:
            if m1 is not None or m2 is not None:
                return False
        elif not np.isclose(m1, m2, rtol, atol):
            return False

        length = distance(self.p1, self.p2)
        dist_p1 = distance(self.p1, point)
        dist_p2 = distance(self.p2, point)
        if dist_p1 > length or dist_p2 > length:
            return False
        return True

    def minmax(self):
        """ Die Funktion bestimmt das Minimum und Maximum auf der x- und der
            y-Achse (return [<min-x>, <max-x>, <min-y>, <max-y>])
        """
        return [min(self.p1[0], self.p2[0]), max(self.p1[0], self.p2[0]),
                min(self.p1[1], self.p2[1]), max(self.p1[1], self.p2[1])]

    def minmax_from_center(self, center):
        """ Die Funktion ermittelt den minimalen und maximalen Abstand vom Center
        """
        dist_max = max(distance(center, self.p1), distance(center, self.p2))
        dist_min = min(distance(center, self.p1), distance(center, self.p2))
        return (dist_min, dist_max)

    def minmax_angle_from_center(self, center):
        alpha_p1 = alpha_line(center, self.p1)
        alpha_p2 = alpha_line(center, self.p2)
        if alpha_angle(alpha_p1, alpha_p2) < np.pi:
            return (alpha_p1, alpha_p2)
        else:
            return (alpha_p2, alpha_p1)

    def get_nodes(self, parts=8):
        """ Die Funktion liefert eine Liste von virtuellen Nodes, welche man
            zum Rechnen der convex_hull() benötigt.
        """
        return (self.p1, self.p2)

    def get_angle_of_arc(self):
        return 0.0

    def __str__(self):
        return "Line p1={}, p2={}".format(self.p1, self.p2)

    def __eq__(self, other):
        """Override the default Equals behavior"""
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        """Define a non-equality test"""
        return not self == other

    def __hash__(self):
        """ Override the default hash behavior
            (that returns the id or the object)
        """
        return hash(tuple(sorted(self.__dict__.items())))


#############################
#       Point (Shape)       #
#############################

class Point(Shape):
    """ used for plotting only """
    def __init__(self, p):
        self.p1 = p

    def render(self, renderer):
        renderer.point(self.p1)
