import os.path
from pathlib import Path
from os.path import join as pjoin
import glob
import numpy as np
from numpy.testing import assert_allclose
from refnx._lib import flatten

import refellips
from refellips import (
    RI,
    DataSE,
    ReflectModelSE,
    ObjectiveSE,
    Cauchy,
    Lorentz,
    MixedSlabSE,
    load_material,
)


pth = Path(os.path.dirname(os.path.abspath(refellips.__file__)))


def test_cauchy_against_wvase():
    # Check the cauchy model behaves as expected
    A = 1.47
    B = 0.00495
    C = 0

    cauchy = Cauchy(A=A, B=B, C=C)

    _f = pth / "tests" / "Cauchynk_fromWVASE.txt"
    wvase_output = np.loadtxt(_f)
    wavs = wvase_output[:, 0]
    refin = A + B / ((wavs / 1000) ** 2) + C / ((wavs / 1000) ** 4)

    refellips_RI = [cauchy.complex(wav).real for wav in wavs]

    assert_allclose(refellips_RI, wvase_output[:, 1], rtol=0.000001)
    assert_allclose(refellips_RI, refin, rtol=0.000001)


def test_RI_from_array():
    A = 1.47
    B = 0.00495
    C = 0

    wavs = np.arange(1, 101.0)
    ri_in = A + B / ((wavs) ** 2) + C / ((wavs) ** 4)
    ec_in = np.linspace(0.01, 0.2, 100)

    _f = RI((wavs, ri_in, ec_in))
    assert_allclose(_f._wav[0], 1000.0)
    ri = _f.complex(2000.0)
    assert_allclose(ri, complex(ri_in[1], ec_in[1]))


def test_lorentz():
    A = [5, 10]
    B = [0.25, 0.5]
    E = [2, 4]
    Einf = 2
    lo = Lorentz(A, B, E, Einf)
    assert len(lo.Am) == 2

    lo.complex(500)
    lo.complex(np.linspace(350, 700, 100))
    lo.epsilon(np.linspace(1, 5))

    data = DataSE(pth / "tests" / "WVASE_lorentz.dat")

    air = load_material("air")
    silicon = load_material("silicon")
    silica = load_material("silica")
    film = Lorentz(A, B, E, Einf)
    s = air | film(1000) | silica(25) | silicon()
    model = ReflectModelSE(s)

    wavelength_aoi = np.c_[
        data.wavelength, np.full_like(data.wavelength, data.aoi)
    ]
    psi, delta = model.model(wavelength_aoi)

    # these tolerances are much larger than we'd like
    assert_allclose(psi, data.psi, rtol=0.07)
    assert_allclose(delta, data.delta, rtol=0.03)


def test_dispersions_are_loadable():
    # test that all the bundled dispersion curves are loadable
    materials = glob.glob(str(pth / "materials" / "*.csv"))
    for material in materials:
        _f = RI(material)
        assert len(_f._wav) > 1


def test_mixedslab():
    a = load_material("water")
    b = Cauchy(A=1.47, B=0.00495)

    slab = MixedSlabSE(10, a, b, 0.5, 3)
    assert b.A in flatten(slab.parameters)
    assert slab.slabs().shape == (1, 5)
    assert_allclose(slab.vf_B.value, 0.5)

    a.wavelength = 400
    b.wavelength = 400
    riac = a.complex(400)
    ribc = b.complex(400)

    slab.vf_B.value = 0
    assert_allclose(slab.slabs()[0, 1], np.real(riac))
    assert_allclose(slab.slabs()[0, 2], np.imag(riac))

    slab.vf_B.value = 0.25
    overall = np.sqrt(0.75 * riac**2 + 0.25 * ribc**2)
    assert_allclose(slab.slabs()[0, 1], np.real(overall))
    assert_allclose(slab.slabs()[0, 2], np.imag(overall))
