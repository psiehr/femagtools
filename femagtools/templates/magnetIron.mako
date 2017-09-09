
m.magn_rad       = da2/2
m.yoke_rad       = dy2/2

m.magn_height     =    ${model.get(['magnet','magnetIron', 'magn_height'])*1e3}
m.magn_width      =    ${model.get(['magnet','magnetIron', 'magn_width'])*1e3}
m.gap_ma_iron     =    ${model.get(['magnet','magnetIron', 'gap_ma_iron'])*1e3}
m.air_triangle    =    ${model.get(['magnet','magnetIron', 'air_triangle'])}
m.iron_height     =    ${model.get(['magnet','magnetIron', 'iron_height'])*1e3}
m.magn_rem        =    ${model.get(['magnet','magnetIron', 'magn_rem'])}
m.shaft_rad      =     ${model.get(['magnet','magnetIron', 'condshaft_r'])*1e3}
m.magn_ori        =    ${model.get(['magnet','magnetIron', 'magn_ori'])}
m.bridge_height   =    ${model.get(['magnet','magnetIron', 'bridge_height'])*1e3}
m.bridge_width    =    ${model.get(['magnet','magnetIron', 'bridge_width'])*1e3}
m.iron_shape      =    ${model.get(['magnet','magnetIron', 'iron_shape'])*1e3}

m.zeroangl        =     0.0

m.mcvkey_yoke     =   mcvkey_yoke
m.nodedist        =   ${model.magnet.get('nodedist',1)}

 pre_models("Magnet in Iron")

%if isinstance(model.get(['magnet','material'],0), dict):
orient = ${model.magnet['material'].get('orient', 'mpolaniso')}
mcv = '${model.magnet['material']['name']}'
rlen = ${model.magnet['material'].get('rlen', 1)*100}
cond = ${model.magnet['material'].get('cond', 625e3)}

for i = 0, m.npols_gen-1 do
    x0, y0 = pr2c(m.magn_rad*math.cos(math.pi/m.num_poles)) - m.magn_height/2,
                  (2*i+1)*math.pi/m.num_poles)
    if i % 2 == 0 then
        def_mat_pm_nlin(x0, y0, red, mcv, 0, orient, cond, rlen)
    else
        def_mat_pm_nlin(x0, y0, green, mcv, 180, orient, cond, rlen)
    end
end
%endif
