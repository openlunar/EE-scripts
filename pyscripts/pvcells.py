from math import exp
from scipy.special import lambertw
from PySpice.Spice.Netlist import Circuit

boltz = 1.38064852e-23
zeroC = 273.15
qe    = 1.60217662e-19

class PVCell:
    def __init__(self, voc, vmp, imp, isc, a, nomtemp = 298.15, tempco = None):
        self.voc, self.isc = voc, isc
        self.vmp, self.imp = vmp, imp
        self.a, self.nomtemp = a, nomtemp
        tc_specs = ('voc', 'vmp', 'imp', 'isc')
        if tempco is None:
            # nothing passed, safest thing is to do nothing I guess
            tempco = {k: 0 for k in tc_specs}
        self.tempco = {}
        for spec in tc_specs:
            if spec not in tempco:
                raise ValueError('tempco must have specs: {}'.format(tc_specs))
            self.tempco[spec] = tempco[spec]

    def specs(self, temp=None):
        if temp is None:
            temp = self.nomtemp
        #TODO want to warn about no actual tempco data?
        return {k: getattr(self, k) + self.tempco[k] * (temp - self.nomtemp)
                for k in ('voc', 'vmp', 'imp', 'isc')}

    def five_elt(self, temp = None):
        if temp is None:
            temp = self.nomtemp
        specs = self.specs(temp)
        
        # using the technique from Cubas, 2014
        voc, isc = specs['voc'], specs['isc']
        vmp, imp = specs['vmp'], specs['imp']
        a = self.a

        vt = boltz * temp / qe

        A = a * vt / imp
        B = -1 * vmp * (2 * imp - isc) / (vmp * isc + voc * (imp - isc))
        C = ((vmp * isc - voc * imp) / (vmp * isc + voc * (imp - isc))
             - (2 * vmp - voc) / (a * vt))
        D = (vmp - voc) / (a * vt)
        Rs = A * (lambertw(B * exp(C), -1) - (D + C))
        
        Rsh = ((vmp - imp * Rs) * (vmp - Rs * (isc - imp) - a * vt)
               / ((vmp - imp * Rs) * (isc - imp) - a * vt * imp))
        Io = ((Rsh + Rs) * isc - voc) / (Rsh * exp(voc / (a * vt)))
        Ipv = (Rsh + Rs) * isc / Rsh
        
        ret = {'rs': Rs, 'rsh': Rsh, 'io': Io, 'ipv': Ipv, 'a': a, 'temp': temp}
        for k,v in ret.items():
            if abs(v.imag) > 0.001 or abs(v.imag) > 0.001 * abs(v.real):
                #TODO make this a warning, not some noisy print
                print("! wait what? Imaginary component to {}: {}".format(k, v))
            ret[k] = v.real
        return ret
    
    def as_spice(self, temp=None):
        elts = self.five_elt(temp)
        return '\n'.join(['.SUBCKT pvcell neg pos PARAMS: Illumination=1',
            '.model foo D (IS={} N={} TNOM={})'.format(elts['io'], elts['a'],
                                                       elts['temp'] - zeroC),
            'Isrc neg internal DC {{Illumination * {}}}'.format(elts['ipv']),
            'Dfoo internal neg foo',
            'Rsh internal neg {}'.format(elts['rsh']),
            'Rs internal pos {}'.format(elts['rs']),
            '.ENDS pvcell\n'
            ])

    def iv_curve(self, temp=None, vmin=1e-3, imin=1e-3):
        if temp is None:
            temp = self.nomtemp
        elts = self.five_elt(temp)
        ckt = Circuit('Performance Sweep')
        d = ckt.model('foo', 'D', IS=elts['io'], N=elts['a'],
                      TNOM=(temp - zeroC))
        ckt.I('src', ckt.gnd, 1, elts['ipv'])
        ckt.D('diode', 1, ckt.gnd, model='foo')
        ckt.R('sh', 1, ckt.gnd, elts['rsh'])
        ckt.R('s', 1, 'out', elts['rs'])
        ckt.R('load', 'out', ckt.gnd, 1)
        ckt['Rload'].plus.add_current_probe(ckt)
        rmin, rmax = 1e-2, 1e5
        _vmin, _imin = vmin * 2, imin * 2
        while _vmin > vmin and _imin > imin:
            if _vmin > vmin:
                rmin /= 10
                ckt['Rload'].resistance = rmin
                res = ckt.simulator(temperature=(temp-zeroC)).operating_point()
                _vmin = float(res.nodes['out'])
            if _imin > imin:
                rmax *= 10
                ckt['Rload'].resistance = rmax
                res = ckt.simulator(temperature=(temp-zeroC)).operating_point()
                _imin = float(res.branches['vrload_plus'])
        
        results = self._sweep_res(ckt, rmin, rmax, temp)
        results['pout'] = [v * a for v,a in zip(results['vout'],
                                                results['aout'])]
        results['Isc'] = results['aout'][0]
        results['Voc'] = results['vout'][-1]
        results['mpp'] = results['pout'].index(max(results['pout']))
        return results

    def _sweep_res(self, circuit, rmin, rmax, temp):
        rlo, rhi = rmin, rmax
        min_chg = 0.01
        stack = [(rlo, rhi)]
        def calc(r):
            circuit['Rload'].resistance = r
            res = circuit.simulator(temperature=(temp - zeroC)).operating_point()
            return (float(res.nodes['out']), float(res.branches['vrload_plus']))
        
        def precise_enough(a, b, minabs=0.002, percent=0.03):
            for (ax, bx) in zip(a, b):
                delta = abs(ax - bx)
                if delta < minabs:
                    return True
                if ax != 0:
                    if abs(delta / ax) > percent:
                        return False
                elif bx != 0:
                    if abs(delta / bx) > percent:
                        return False
            return True
        
        results = {rlo : calc(rlo), rhi : calc(rhi)}
        while len(stack):
            rlo, rhi = stack.pop()
            if precise_enough(results[rlo], results[rhi]):
                continue
            rmid = (rlo + rhi) / 2
            results[rmid] = calc(rmid)
            stack.extend([(rlo, rmid), (rmid, rhi)])
        r_sorted = sorted(results.keys())
        return {'r'   : r_sorted,
                'vout': [results[r][0] for r in r_sorted],
                'aout': [results[r][1] for r in r_sorted]
               }
