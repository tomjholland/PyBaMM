from __future__ import annotations

import pybamm
from datetime import datetime
import json
import importlib
import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pybamm import BaseBatteryModel


class Serialise:
    """
    Converts a discretised model to and from a JSON file.

    """

    def __init__(self):
        pass

    class _SymbolEncoder(json.JSONEncoder):
        """Converts PyBaMM symbols into a JSON-serialisable format"""

        def default(self, node: dict):
            node_dict = {"py/object": str(type(node))[8:-2], "py/id": id(node)}
            if isinstance(node, pybamm.Symbol):
                node_dict.update(node.to_json())  # this doesn't include children
                node_dict["children"] = []
                for c in node.children:
                    node_dict["children"].append(self.default(c))

                if hasattr(node, "initial_condition"):  # for ExplicitTimeIntegral
                    node_dict["initial_condition"] = self.default(
                        node.initial_condition
                    )

                return node_dict

            if isinstance(node, pybamm.Event):
                node_dict.update(node.to_json())
                node_dict["expression"] = self.default(node._expression)
                return node_dict

            json_obj = json.JSONEncoder.default(self, node)  # pragma: no cover
            node_dict["json"] = json_obj
            return node_dict

    class _MeshEncoder(json.JSONEncoder):
        """Converts PyBaMM meshes into a JSON-serialisable format"""

        def default(self, node: dict):
            node_dict = {"py/object": str(type(node))[8:-2], "py/id": id(node)}
            if isinstance(node, pybamm.Mesh):
                node_dict.update(node.to_json())

                node_dict["sub_meshes"] = {}
                for k, v in node.items():
                    if len(k) == 1 and "ghost cell" not in k[0]:
                        node_dict["sub_meshes"][k[0]] = self.default(v)

                return node_dict

            if isinstance(node, pybamm.SubMesh):
                node_dict.update(node.to_json())
                return node_dict

            json_obj = json.JSONEncoder.default(self, node)  # pragma: no cover
            node_dict["json"] = json_obj
            return node_dict

    class _Empty:
        """A dummy class to aid deserialisation"""

        pass

    class _EmptyDict(dict):
        """A dummy dictionary class to aid deserialisation"""

        pass

    def save_model(
        self,
        model: pybamm.BaseBatteryModel,
        mesh: pybamm.Mesh = None,
        variables: pybamm.FuzzyDict = None,
        filename: str = None,
    ):
        """
        Saves a discretised model to a JSON file.

        As the model is discretised and ready to solve, only the right hand side,
        algebraic and initial condition variables are saved.

        Parameters
        ----------
        model: : :class:`pybamm.BaseBatteryModel`
            The discretised model to be saved
        mesh: :class: `pybamm.Mesh`, optional
            The mesh the model has been discretised over. Not neccesary to solve
            the model when read in, but required to use pybamm's plotting tools.
        variables: :class: `pybamm.FuzzyDict`, optional
            The discretised model varaibles. Not necessary to solve a model, but
            required to use pybamm's plotting tools.
        filename: str, optional
            The desired name of the JSON file. If no name is provided, one will be
            created based on the model name, and the current datetime.
        """
        if model.is_discretised == False:
            raise NotImplementedError(
                "PyBaMM can only serialise a discretised, ready-to-solve model."
            )

        model_json = {
            "py/object": str(type(model))[8:-2],
            "py/id": id(model),
            "name": model.name,
            "options": model.options,
            "bounds": [bound.tolist() for bound in model.bounds],
            "concatenated_rhs": self._SymbolEncoder().default(model._concatenated_rhs),
            "concatenated_algebraic": self._SymbolEncoder().default(
                model._concatenated_algebraic
            ),
            "concatenated_initial_conditions": self._SymbolEncoder().default(
                model._concatenated_initial_conditions
            ),
            "events": [self._SymbolEncoder().default(event) for event in model.events],
            "mass_matrix": self._SymbolEncoder().default(model.mass_matrix),
            "mass_matrix_inv": self._SymbolEncoder().default(model.mass_matrix_inv),
        }

        if mesh:
            model_json["mesh"] = self._MeshEncoder().default(mesh)

        if variables:
            model_json["geometry"] = dict(model._geometry)
            model_json["variables"] = {
                k: self._SymbolEncoder().default(v) for k, v in dict(variables).items()
            }

        if filename is None:
            filename = model.name + "_" + datetime.now().strftime("%Y_%m_%d-%p%I_%M_%S")

        with open(filename + ".json", "w") as f:
            json.dump(model_json, f)

    def load_model(
        self, filename: str, battery_model: BaseBatteryModel = None
    ) -> BaseBatteryModel:
        """
        Loads a discretised, ready to solve model into PyBaMM.

        A new pybamm battery model instance will be created, which can be solved
        and the results plotted as usual.

        Currently only available for pybamm models which have previously been written
        out using the `save_model()` option.

        Warning: This only loads in discretised models. If you wish to make edits to the
        model or initial conditions, a new model will need to be constructed seperately.

        Parameters
        ----------

        filename: str
            Path to the JSON file containing the serialised model file
        battery_model: :class: pybamm.BaseBatteryModel, optional
            PyBaMM model to be created (e.g. pybamm.lithium_ion.SPM), which will override
            any model names within the file. If None, the function will look for the saved object
            path, present if the original model came from PyBaMM.

        Returns
        -------
        :class: pybamm.BaseBatteryModel
            A PyBaMM model object, of type specified either in the JSON or in `battery_model`.
        """

        with open(filename, "r") as f:
            model_data = json.load(f)

        recon_model_dict = {
            "name": model_data["name"],
            "options": model_data["options"],
            "bounds": tuple(np.array(bound) for bound in model_data["bounds"]),
            "concatenated_rhs": self._reconstruct_epression_tree(
                model_data["concatenated_rhs"]
            ),
            "concatenated_algebraic": self._reconstruct_epression_tree(
                model_data["concatenated_algebraic"]
            ),
            "concatenated_initial_conditions": self._reconstruct_epression_tree(
                model_data["concatenated_initial_conditions"]
            ),
            "events": [
                self._reconstruct_epression_tree(event)
                for event in model_data["events"]
            ],
            "mass_matrix": self._reconstruct_epression_tree(model_data["mass_matrix"]),
            "mass_matrix_inv": self._reconstruct_epression_tree(
                model_data["mass_matrix_inv"]
            ),
        }

        recon_model_dict["geometry"] = (
            model_data["geometry"] if "geometry" in model_data.keys() else None
        )

        recon_model_dict["mesh"] = (
            self._reconstruct_mesh(model_data["mesh"])
            if "mesh" in model_data.keys()
            else None
        )

        recon_model_dict["variables"] = (
            {
                k: self._reconstruct_epression_tree(v)
                for k, v in model_data["variables"].items()
            }
            if "variables" in model_data.keys()
            else None
        )

        if battery_model:
            return battery_model.deserialise(recon_model_dict)

        if "py/object" in model_data.keys():
            model_framework = self._get_pybamm_class(model_data)
            return model_framework.deserialise(recon_model_dict)

        raise TypeError(
            """
            The PyBaMM battery model to use has not been provided.
            """
        )

    def _get_pybamm_class(self, snippet: dict):
        """Find a pybamm class to initialise from object path"""
        parts = snippet["py/object"].split(".")
        try:
            module = importlib.import_module(".".join(parts[:-1]))
        except Exception as ex:
            print(ex)

        class_ = getattr(module, parts[-1])

        try:
            empty_class = self._Empty()
            empty_class.__class__ = class_
        except:
            empty_class = self._EmptyDict()
            empty_class.__class__ = class_

        return empty_class

    def _reconstruct_symbol(self, dct: dict):
        """Reconstruct an individual pybamm Symbol"""
        symbol_class = self._get_pybamm_class(dct)
        symbol = symbol_class._from_json(dct)
        return symbol

    def _reconstruct_epression_tree(self, node: dict):
        """
        Loop through an expression tree creating pybamm Symbol classes

        Conducts post-order tree traversal to turn each tree node into a
        `pybamm.Symbol` class, starting from leaf nodes without children and
        working upwards.

        Parameters
        ----------
        node: dict
            A node in an expression tree.
        """
        if "children" in node:
            for i, c in enumerate(node["children"]):
                child_obj = self._reconstruct_epression_tree(c)
                node["children"][i] = child_obj
        elif "expression" in node:
            expression_obj = self._reconstruct_epression_tree(node["expression"])
            node["expression"] = expression_obj

        obj = self._reconstruct_symbol(node)

        return obj

    def _reconstruct_mesh(self, node: dict):
        """Reconstructs a Mesh object"""
        if "sub_meshes" in node:
            for k, v in node["sub_meshes"].items():
                sub_mesh = self._reconstruct_symbol(v)
                node["sub_meshes"][k] = sub_mesh

        new_mesh = self._reconstruct_symbol(node)

        return new_mesh
