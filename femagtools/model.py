# -*- coding: utf-8 -*-
"""
    femagtools.model
    ~~~~~~~~~~~~~~~~

    Managing model parameters



"""
import logging

logger = logging.getLogger(__name__)


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    if a or b:
        return abs(a*b)/gcd(a, b)
    return 0


class MCerror(Exception):
    pass


class Model(object):
    def __init__(self, parameters):
        if isinstance(parameters, dict):
            for k in parameters.keys():
                setattr(self, k, parameters[k])

    def set_value(self, name, value, p=None):
        """set value of parameter identified by name

        Args:
            name: name of parameter
            value: value to be assigned to parameter
        """
        if isinstance(name, str):
            setattr(self, name, value)
            return

        if len(name) > 1:
            k = name[0]
            if hasattr(self, k):
                self.set_value(name[1:], value, getattr(self, k))
                return
            elif p:
                self.set_value(name[1:], value, p[k])
                return
            self.set_value(name[1:], value, self)
            return
        if p:
            p[name[0]] = value
            return
        setattr(self, name[0], value)

    def get(self, name, r=None):
        """return value of key name

        Args:
            name: key of parameter value

        Return:
            value of parameter identified by key
        """
        try:
            if isinstance(name, str):
                if r is not None:
                    return getattr(self, name, r)
                return getattr(self, name)
            if r and type(r) == dict:
                for k in name:
                    r = r.get(k)
                return r
            if len(name) > 1:
                if r:
                    return self.get(name[1:], getattr(r, name[0]))
                return self.get(name[1:], getattr(self, name[0]))
            return getattr(self, name[0])
        except KeyError as e:
            logger.error(e)
            raise MCerror(e)

    def __str__(self):
        "return string format of this object"
        return repr(self.__dict__)

    def __repr__(self):
        "representation of this object"
        return self.__str__()


class MachineModel(Model):
    """represents a machine model for a FE analysis

    Args:
      parameters: string or dict containing the model parameters. For example:
    ::

        {'lfe': 0.1,
        'poles': 4,
        'outer_diam': 0.13,
        'bore_diam': 0.07,
        'stator':{
        'num_slots': 12,
        'num_slots_gen': 3,
        ...
        },
        'magnet':{
            'material': 'M395',
            ..
        }
        }

        if parameters is string it is interpreted as the model name.
    """
    def __init__(self, parameters):
        super(self.__class__, self).__init__(parameters)
        name = 'DRAFT'
        if isinstance(parameters, str):
            name = parameters
        elif 'name' in parameters:
            name = parameters['name']
        # must replace white space
        name = name.strip().replace(' ', '_')
        for c in ('"', '(', ')'):
            name = name.replace(c, '')
        setattr(self, 'name', name)
        try:
            self.external_rotor = (self.external_rotor == 1)
        except:
            self.external_rotor = False
        self.move_inside = 1.0 if self.external_rotor else 0.0
        if 'magnet' in parameters:
            if 'mcvkey_mshaft' in self.magnet:
                self.magnet['mcvkey_shaft'] = self.magnet['mcvkey_mshaft']
            for mcv in ('mcvkey_yoke', 'mcvkey_shaft'):
                if mcv not in self.magnet:
                    self.magnet[mcv] = 'dummy'
        if 'coord_system' in parameters:
            self.move_action = 1
        else:
            self.coord_system = 0
            self.move_action = 0

        if 'stator' in parameters and 'num_slots_gen' not in self.stator:
            try:
                m = self.windings['num_phases']
            except:
                m = 1

            try:
                self.stator['num_slots_gen'] = (m*self.stator['num_slots'] /
                                                gcd(self.stator['num_slots'],
                                                    m*self.poles))
            except:
                pass

    def set_num_slots_gen(self):
        if 'num_slots_gen' not in self.stator:
            try:
                m = self.windings['num_phases']
            except:
                m = 1

            try:
                self.stator['num_slots_gen'] = (m*self.stator['num_slots'] /
                                                gcd(self.stator['num_slots'],
                                                    m*self.poles))
            except:
                pass

    def set_mcvkey_magnet(self, mcvkey):
        self.mcvkey_magnet = mcvkey

    def get_mcvkey_magnet(self):
        try:
            return self.mcvkey_magnet
        except:
            return ''

    def set_magcurves(self, magcurves, magnetmat={}):
        """set and return real names of magnetizing curve material

        Args:
            magcurves: :class: 'MagnetizingCurve' including
                              magnetizing curve materials

        Return:
            set of magnetizing curve names attached to this model

        """
        names = []
        missing = []
        if magcurves:
            if 'stator' in self.__dict__:
                try:
                    if self.stator['mcvkey_yoke'] != 'dummy':
                        mcv = magcurves.find(self.stator['mcvkey_yoke'])
                        if mcv:
                            logger.debug('stator mcv %s', mcv)
                            self.stator['mcvkey_yoke'] = mcv
                            names.append(mcv)
                        else:
                            missing.append(self.stator['mcvkey_yoke'])
                            logger.error('stator mcv %s not found',
                                         self.stator['mcvkey_yoke'])
                except KeyError:
                    pass

            if 'magnet' in self.__dict__:
                try:
                    if self.magnet['mcvkey_yoke'] != 'dummy':
                        mcv = magcurves.find(self.magnet['mcvkey_yoke'])
                        if mcv:
                            logger.debug('magnet mcv %s', mcv)
                            self.magnet['mcvkey_yoke'] = mcv
                            names.append(mcv)
                        else:
                            missing.append(self.magnet['mcvkey_yoke'])
                            logger.error('magnet mcv %s not found',
                                         self.magnet['mcvkey_yoke'])
                except KeyError:
                    pass

                try:
                    if self.magnet['mcvkey_shaft'] != 'dummy':
                        mcv = magcurves.find(self.magnet['mcvkey_shaft'])
                        if mcv:
                            logger.debug('shaft mcv %s', mcv)
                            self.magnet['mcvkey_shaft'] = mcv
                            names.append(mcv)
                        else:
                            missing.append(self.magnet['mcvkey_shaft'])
                            logger.error('magnet shaft %s not found',
                                         self.magnet['mcvkey_shaft'])
                except KeyError:
                    pass

        if magnetmat and 'magnet' in self.__dict__:
            try:
                magnet = magnetmat.find(self.magnet['material'])
                if magnet and 'mcvkey' in magnet:
                    mcv = magcurves.find(magnet['mcvkey'])
                    if mcv:
                        logger.debug('magnet mcv %s', mcv)
                        self.magnet['mcvkey_magnet'] = mcv
                        names.append(mcv)
                    else:
                        missing.append(magnet['mcvkey'])
                        logger.error('magnet mcv %s not found',
                                     magnet['mcvkey'])
            except KeyError:
                pass
            except AttributeError:
                if 'material' in self.magnet:
                    missing.append(self.magnet['material'])
                    logger.error('magnet mcv %s not found',
                                 self.magnet['material'])

        if missing:
            raise MCerror("MC pars missing: {}".format(
                ', '.join(set(missing))))
        return set(names)

    def statortype(self):
        """return type of stator slot"""
        for k in self.stator:
            if isinstance(self.stator[k], dict):
                return k
        raise MCerror("Missing stator slot model in {}".format(self.stator))

    def magnettype(self):
        """return type of magnet slot"""
        for k in self.magnet:
            if k != 'material' and isinstance(self.magnet[k], dict):
                return k
        raise MCerror("Missing magnet model in {}".format(self.magnet))

    def is_complete(self):
        """check completeness of models"""
        try:
            self.statortype()
            self.magnettype()
            return True
        except:
            return False

    def is_dxffile(self):
        if 'dxffile' in self.__dict__:
            if isinstance(self.dxffile, dict):
                return True
        return False


class FeaModel(Model):
    def __init__(self, parameters):
        self.cufilfact = 0.45
        self.culength = 1.4
        self.wind_temp = 20
        self.slot_indul = 0.0
        self.skew_angle = 0.0
        self.num_skew_steps = 0
        self.num_par_wdgs = 1
        self.eval_force = 0
        self.optim_i_up = 0
        self.plots = []
        self.airgap_induc = []
        super(self.__class__, self).__init__(parameters)
