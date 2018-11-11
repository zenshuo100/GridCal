from GridCal.Engine.PowerFlowDriver import PowerFlowOptions, SolverType, ReactivePowerControlMode
from GridCal.Engine.PowerFlowDriver import PowerFlow
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.Devices import *
from GridCal.Engine.DeviceTypes import *

test_name = "test_pv_1"
Sbase = 100 # MVA

def complexe(z, XR):
    """
    Returns the complex impedance from z (in %) and the X/R ratio.
    """
    z = float(abs(z))
    XR = float(abs(XR))
    real = (z**2/(1+XR**2))**0.5
    try:
        imag = (z**2/(1+1/XR**2))**0.5
    except ZeroDivisionError:
        imag = 0.0
    return complex(real, imag)

def test_pv_1():
    """
    Voltage controlled generator test, also useful for a basic tutorial. In this
    case the generator M32 regulates the voltage at a setpoint of 1.025 pu, and
    the slack bus (POI) regulates it at 1.0 pu.

    The transformers' magnetizing branch losses are considered, but their
    voltage regulators aren't.
    """
    grid = MultiCircuit(name=test_name)
    grid.Sbase = Sbase
    grid.time_profile = None
    grid.logger = list()

    # Create buses
    POI = Bus(name="POI",
              vnom=100, #kV
              is_slack=True)
    grid.add_bus(POI)

    B_MV_M32 = Bus(name="B_MV_M32",
                   vnom=10) #kV
    grid.add_bus(B_MV_M32)

    B_LV_M32 = Bus(name="B_LV_M32",
                   vnom=0.6) #kV
    grid.add_bus(B_LV_M32)

    # Create voltage controlled generators (or slack, a.k.a. swing)
    UT = ControlledGenerator(name="Utility")
    UT.bus = POI
    grid.add_controlled_generator(POI, UT)

    M32 = ControlledGenerator(name="M32",
                              active_power=4.2,
                              voltage_module=1.025,
                              Qmin=-2.5,
                              Qmax=2.5)
    M32.bus = B_LV_M32
    grid.add_controlled_generator(B_LV_M32, M32)

    # Create transformer types
    s = 100 # MVA
    z = 8 # %
    xr = 40
    SS = TransformerType(name="SS",
                         hv_nominal_voltage=100, # kV
                         lv_nominal_voltage=10, # kV
                         nominal_power=s,
                         copper_losses=complexe(z, xr).real*s*1000/Sbase,
                         iron_losses=125, # kW
                         no_load_current=0.5, # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(SS)

    s = 5 # MVA
    z = 6 # %
    xr = 20
    PM = TransformerType(name="PM",
                         hv_nominal_voltage=10, # kV
                         lv_nominal_voltage=0.6, # kV
                         nominal_power=s,
                         copper_losses=complexe(z, xr).real*s*1000/Sbase,
                         iron_losses=6.25, # kW
                         no_load_current=0.5, # %
                         short_circuit_voltage=z)
    grid.add_transformer_type(PM)

    # Create branches
    X_C3 = Branch(bus_from=POI,
                  bus_to=B_MV_M32,
                  name="X_C3",
                  branch_type=BranchType.Transformer,
                  template=SS)
    grid.add_branch(X_C3)

    X_M32 = Branch(bus_from=B_MV_M32,
                   bus_to=B_LV_M32,
                   name="X_M32",
                   branch_type=BranchType.Transformer,
                   template=PM)
    grid.add_branch(X_M32)

    # Apply templates (device types)
    grid.apply_all_branch_types()

    print("Buses:")
    for i, b in enumerate(grid.buses):
        print(f" - bus[{i}]: {b}")
    print()

    grid.compile()
    options = PowerFlowOptions(SolverType.LM,
                               verbose=True,
                               robust=True,
                               initialize_with_existing_solution=True,
                               multi_core=True,
                               control_q=ReactivePowerControlMode.Direct,
                               tolerance=1e-6,
                               max_iter=99)

    power_flow = PowerFlow(grid, options)
    power_flow.run()

    approx_volt = [round(100*abs(v), 1) for v in power_flow.results.voltage]
    solution = [100.0, 100.1, 102.5] # Expected solution from GridCal and ETAP 16.1.0, for reference

    print()
    print(f"Test: {test_name}")
    print(f"Results:  {approx_volt}")
    print(f"Solution: {solution}")
    print()

    print("Controlled generators:")
    for g in grid.get_controlled_generators():
        print(f" - Generator {g}: q_min={g.Qmin}pu, q_max={g.Qmax}pu")
    print()

    print("Branches:")
    for b in grid.branches:
        print(f" - {b}:")
        print(f"   R = {round(b.R, 4)} pu")
        print(f"   X = {round(b.X, 4)} pu")
        print(f"   X/R = {round(b.X/b.R, 1)}")
        print(f"   G = {round(b.G, 4)} pu")
        print(f"   B = {round(b.B, 4)} pu")
    print()

    print("Transformer types:")
    for t in grid.transformer_types:
        print(f" - {t}: Copper losses={int(t.Copper_losses)}kW, Iron losses={int(t.Iron_losses)}kW, SC voltage={t.Short_circuit_voltage}%")
    print()

    print("Losses:")
    for i in range(len(grid.branches)):
        print(f" - {grid.branches[i]}: losses={1000*round(power_flow.results.losses[i], 3)} kVA")
    print()

    equal = True
    for i in range(len(approx_volt)):
        if approx_volt[i] != solution[i]:
            equal = False

    assert equal