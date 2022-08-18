import pybamm
import numpy as np
import matplotlib.pyplot as plt
import itertools


parameters = [
    "Marquis2019",
    "Prada2013",
    "Ramadass2004",
    "Chen2020",
]
models = [pybamm.lithium_ion.SPM(), pybamm.lithium_ion.DFN()]
model_names = ["SPM","DFN"]
abstols = [
    0.001,
    0.0001,
    1.0e-5,
    1.0e-6,
    1.0e-7,
    1.0e-8,
    1.0e-9,
    1.0e-10,
    1.0e-11,
    1.0e-12,
    1.0e-13,
]
solvers = [
    pybamm.IDAKLUSolver()
     ,
      pybamm.CasadiSolver(), pybamm.CasadiSolver( mode="fast")]
solver_names = [
    "IDAKLU",
     "Casadi - safe", "Casadi - fast"]
nrow = len(solvers)

ncol = len(models)
fig, axs = plt.subplots(len(solvers), len(models),figsize=(8, 5))

for  ax,i,j in zip(axs.ravel(),itertools.product(models,solvers),itertools.product(model_names,solver_names)):
                # ax.plot()
                for params in parameters:
                    time_points = []
                    solver = i[1]

                    model = i[0].new_copy()
                    c_rate = 10
                    tmax = 3600 / c_rate
                    nb_points = 500
                    t_eval = np.linspace(0, tmax, nb_points)
                    geometry = model.default_geometry

                    # load parameter values and process model and geometry
                    param = pybamm.ParameterValues(params)
                    param.process_model(model)
                    param.process_geometry(geometry)

                    # set mesh
                    var_pts = {
                        "x_n": 20,
                        "x_s": 20,
                        "x_p": 20,
                        "r_n": 30,
                        "r_p": 30,
                        "y": 10,
                        "z": 10,
                    }
                    mesh = pybamm.Mesh(geometry, model.default_submesh_types, var_pts)

                    # discretise model
                    disc = pybamm.Discretisation(mesh, model.default_spatial_methods)
                    disc.process_model(model)
                    print(ax)
                    i = list(i)
                    print(list(i))
                    # solver = i[1]
                
                    for tol in abstols:
                        print(tol)
                        solver.atol = tol
                        solver.solve(model, t_eval=t_eval)
                        time = 0
                        runs = 20
                        for k in range(0, runs):

                            solution = solver.solve(model, t_eval=t_eval)
                            time += solution.solve_time.value
                        time = time / runs

                        time_points.append(time)


                    ax.set_xscale('log')
                    ax.set_yscale('log')
                    ax.set_xlabel("abstols")
                    ax.set_ylabel("time(s)")
                    # ax.tight_layout()
                    ax.set_title(f"{j[0]} with {j[1]}")
                    ax.plot(abstols, time_points)
                    
plt.tight_layout()
plt.gca().legend(
    parameters,
    loc="upper right",
)
# plt.show()
print("a")
plt.savefig(f"benchmarks/benchmark_images/time_vs_abstols_{pybamm.__version__}.png")


content = f"# PyBaMM {pybamm.__version__}\n## Solve Time vs Abstols\n<img src='./benchmark_images/time_vs_abstols_{pybamm.__version__}.png'>\n"  # noqa

with open("./benchmarks/release_work_precision_sets.md", "r") as original:
    data = original.read()
with open("./benchmarks/release_work_precision_sets.md", "w") as modified:
    modified.write(f"{content}\n{data}")