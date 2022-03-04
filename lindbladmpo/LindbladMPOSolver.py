# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import collections
import subprocess
import uuid
from typing import Dict, Optional
import numpy as np
import platform
import os


class LindbladMPOSolver:
	"""Evolve multi-qubit Lindblad dynamics with a high-performance matrix-product-operators solver."""

	DEFAULT_EXECUTABLE_PATH = '/../bin/lindbladmpo'
	"""Name and location of the solver executable. Will be appended with '.exe' for Windows."""

	DEFAULT_CYGWIN_PATH = "C:/cygwin64/bin/bash.exe"
	"""Default path for the cygwin executable, which is used to invoke the solver (Windows only)."""

	def __init__(self, parameters: Optional[dict] = None,
				 s_cygwin_path: Optional[str] = None, s_solver_path: Optional[str] = None):
		"""Initialize the instance.

		Args:
			parameters: The model parameters.
			s_cygwin_path: On Windows only, indicates the cygwin executable path. A default
				location will be assigned if this argument is not pass.
			s_solver_path: Indicates the solver executable path. A default location will be
				assigned if this argument is not passed.
		"""
		self.parameters = parameters
		self.s_input_file = ''
		self.s_output_path = ''
		s_cygwin_path, s_solver_path = self.process_default_paths(s_cygwin_path, s_solver_path)
		self.s_cygwin_path = s_cygwin_path
		self.s_solver_path = s_solver_path
		self.s_id_suffix = ''
		self.result = {}

	def solve(self):
		"""Solves the simulation and loads the result dictionaries."""
		if self.s_input_file == '':
			self.build()
		exit_code = LindbladMPOSolver.execute(self.s_cygwin_path, self.s_solver_path, self.s_input_file)
		if exit_code != 0:
			raise Exception("There was an error executing the solver.")
		self.result = LindbladMPOSolver.load_output(self.s_output_path)

	@staticmethod
	def process_default_paths(s_cygwin_path: Optional[str] = None,
							  s_solver_path: Optional[str] = None) -> (str, str):
		""" Returns the proper default values for the cygwin path and solver path according to
			the system platform, for each of those parameter that is None, otherwise the parameter
			is returned unchanged.
		Args:
			s_cygwin_path: the path for the cygwin executable (on Windows).
			s_solver_path: the path for the solver executable.
		Returns:
			(s_cygwin_path, s_solver_path): Default values for the cygwin path and solver path
			according to the system platform.
		"""
		if s_cygwin_path is None or s_solver_path is None:
			s_solver_path1 = os.path.dirname(os.path.abspath(__file__))
			s_system = platform.system().lower()
			if s_system == 'windows':
				# On Windows we execute the solver using the cygwin bash, using the default path:
				s_cygwin_path1 = LindbladMPOSolver.DEFAULT_CYGWIN_PATH

				# s_solver_path should be of the form "/cygdrive/c/ ... ", and we use below a path
				# relative to the current file's path in the package
				s_solver_path1 = s_solver_path1.replace(':', '')
				s_solver_path1 = s_solver_path1.replace('\\', '/')
				s_solver_path1 = "/cygdrive/" + s_solver_path1
				s_solver_path1 += LindbladMPOSolver.DEFAULT_EXECUTABLE_PATH + '.exe'
			else:
				s_cygwin_path1 = ''
				s_solver_path1 += LindbladMPOSolver.DEFAULT_EXECUTABLE_PATH
			if s_cygwin_path is None:
				s_cygwin_path = s_cygwin_path1
			if s_solver_path is None:
				s_solver_path = s_solver_path1
		return s_cygwin_path, s_solver_path

	def build(self, parameters: Optional[dict] = None):
		"""Write the parameters dictionary to the `.input.txt` file the solver expects.

		Initializes also the member fields:
			self.s_input_file: File name of solver input file,
			self.s_output_prefix: Prefix for solver output path,
			self.s_id_suffix: The unique id suffix (possibly empty),
			All fields are initialized based on the user settings in the parameters dictionary
			(or default values if not assigned).

		Args:
			parameters: The model parameters.
		"""
		if parameters is not None:
			self.parameters = parameters
		parameters = self.parameters
		check_params = self._virtual_verify_parameters()
		# check if there is a problem with the input, if "" returned there is no problem
		if check_params != "":
			raise Exception(check_params)
		# check if the user defined an input file name
		s_output_path: str = parameters.get("output_files_prefix", "")
		if s_output_path == "" or s_output_path[-1] in ('/', '.', '\\'):
			s_output_path += "lindblad"
		b_uuid = parameters.get("b_unique_id", False)
		if b_uuid:
			s_uuid = uuid.uuid4().hex
			print("Generating a unique id for this simulation: " + s_uuid)
			parameters["unique_id"] = s_uuid
		else:
			s_uuid = parameters.get("unique_id", "")
		s_id_suffix = ''
		if s_uuid != "":
			s_id_suffix = '.' + s_uuid
		s_output_path += s_id_suffix
		s_input_file = s_output_path + ".input.txt"

		b_bond_indices = False
		first_bond_indices = []
		second_bond_indices = []
		interactions = []
		if 'J' in parameters.keys():
			if type(parameters['J']) == np.ndarray:
				interactions.append('J')
		if 'J_z' in parameters.keys():
			if type(parameters['J_z']) == np.ndarray:
				interactions.append('J_z')
		if len(interactions) == 2:
			if parameters['J'].shape == parameters['J_z'].shape:
				b_bond_indices = True
				for i in range(parameters['J'].shape[0]):
					for j in range(parameters['J'].shape[1]):
						if parameters['J'][i, j] != 0 or parameters['J_z'][i, j] != 0:
							first_bond_indices.append(i + 1)
							second_bond_indices.append(j + 1)
			else:
				raise Exception("J and J_z are not of the same size.")
		elif len(interactions) == 1:
			b_bond_indices = True
			for i in range(parameters[interactions[0]].shape[0]):
				for j in range(parameters[interactions[0]].shape[1]):
					if parameters[interactions[0]][i, j] != 0:
						first_bond_indices.append(i + 1)
						second_bond_indices.append(j + 1)

		print("Creating solver input file:")
		s_input_file = s_input_file.replace("\\", "/")
		print(s_input_file)
		file = open(s_input_file, "w")
		for key in parameters.keys():
			if key == "b_unique_id":
				pass
			elif key == "output_files_prefix":
				file.write(key + ' = ' + s_output_path + "\n")
			elif (key == 'J' or key == 'J_z') and type(parameters[key]) == np.ndarray and\
					len(parameters[key]) > 1:
				# check if to create bond indices arrays
				not_first_value = False
				file.write(key + " = ")
				for i in range(len(first_bond_indices)):
					if not_first_value:
						file.write(",")
					file.write(str(parameters[key][first_bond_indices[i] - 1,
												   second_bond_indices[i] - 1]))
					not_first_value = True
				file.write("\n")
			elif type(parameters[key]) == np.ndarray:
				file.write(key + " = ")
				for i in range(parameters[key].shape[0]):
					file.write(str(parameters[key][i]))
					if i + 1 != parameters[key].shape[0]:
						file.write(",")
				file.write("\n")
			elif key == 'init_pauli_state' or key == '1q_components' or key == '2q_components':
				if isinstance(parameters[key], str):
					val_list = [parameters[key]]
				else:
					val_list = parameters[key]
				n_indices = len(val_list)
				file.write(key + " = ")
				for i_op, op in enumerate(val_list):
					file.write(str(op).strip("'"))
					if i_op != n_indices - 1:
						file.write(",")
				file.write("\n")
			elif key == '1q_indices':
				n_indices = len(parameters[key])
				file.write(key + " = ")
				for i_site, site in enumerate(parameters[key]):
					file.write(str(site + 1))
					# +1 because Python indices are 0-based, while iTensor's are 1-based
					if i_site != n_indices - 1:
						file.write(",")
				file.write("\n")
			elif key == '2q_indices' or key == "init_graph_state":
				file.write(key + " = ")
				n_tuples = len(parameters[key])
				for i_2q_tuple, _2q_tuple in enumerate(parameters[key]):
					file.write(str(_2q_tuple[0] + 1) + ',' + str(_2q_tuple[1] + 1))
					# +1 because Python indices are 0-based, while iTensor's are 1-based
					if i_2q_tuple != n_tuples - 1:
						file.write(",")
				file.write("\n")
			else:
				file.write(key + " = " + str(parameters[key]).strip("[]") + "\n")
		if b_bond_indices:
			file.write("first_bond_indices = " +
					   str(first_bond_indices).strip("[]").replace(' ', '') + "\n")
			file.write("second_bond_indices = " +
					   str(second_bond_indices).strip("[]").replace(' ', '') + "\n")
		file.close()
		self.s_input_file = s_input_file
		self.s_output_path = s_output_path
		self.s_id_suffix = s_id_suffix

	@staticmethod
	def execute(s_cygwin_path = None, s_solver_path = None, s_input_file = "") -> int:
		""" Execute the simulation solver.

		Args:
			s_cygwin_path : the path of the cygwin bash terminal execution
			s_solver_path : the path of the simulator executable
			s_input_file : input file path, if empty then the simulator is run using default values.

		Returns:
			exit code : the exit code of the solver.
		"""
		s_cygwin_path, s_solver_path = LindbladMPOSolver.process_default_paths(s_cygwin_path,
																			   s_solver_path)
		if s_cygwin_path:
			call_string = s_cygwin_path + ' --login -c "'
		else:
			call_string = ''
		call_string += s_solver_path
		if s_input_file:
			call_string += " input_file '" + str(s_input_file) + "'"
			if s_cygwin_path:
				call_string += '"'
		print("Executing solver with command:")
		print("\t" + call_string + "\n")

		process = subprocess.Popen(call_string, shell = True)
		exit_code = process.wait()
		print(f"Solver process terminated with exit code {exit_code}.\n")
		return exit_code

	@staticmethod
	def load_output(s_output_path: str):
		""" Read the three solver output files and returns a dictionary with the results.
		Args:
			s_output_path : prefix of the output files path. To this string the corresponding file
				endings according to each output type will be appended.
		Returns:
			result : A dictionary with three dictionaries storing the different output types.
				The contained dictionaries have the format:
				TODO fix: key (tuple) = (qubit (int), operator (string), time (float)) : expectation value (float)
		"""
		result = {}
		s_output_type = 'obs-1q'
		result[s_output_type] = LindbladMPOSolver._read_data_file(s_output_path, s_output_type)
		s_output_type = 'obs-2q'
		result[s_output_type] = LindbladMPOSolver._read_data_file(s_output_path, s_output_type)
		s_output_type = 'global'
		result[s_output_type] = LindbladMPOSolver._read_data_file(s_output_path, s_output_type)
		return result

	@staticmethod
	def _read_data_file(s_output_path: str, s_output_type: str) -> Dict:
		""" Reads one of the solver output files and returns a dictionary with the data.
		Args:
			s_output_path : prefix of the output files path. To this string the corresponding file
				endings according to each output type will be appended.
			s_output_type : A string defining the observable type, one of the 1-qubit, 2-qubits,
				or global observables.
		Returns:
			result : A dictionary with the result, in the format
				TODO fix: key (tuple) = (qubit (int), operator (string), time (float)) : expectation value (float)
		"""
		full_filename = s_output_path + f".{s_output_type}.dat"
		print("Loading output data file: " + full_filename)
		file = open(full_filename, "r")
		result = collections.OrderedDict()
		file.readline()
		for line in file:
			words = line.strip().split()
			if not words:
				continue
			LindbladMPOSolver._read_data_line(s_output_type, words, result)
		file.close()
		return result

	@staticmethod
	def _read_data_line(s_output_type: str, words: list, result: Dict):
		t = float(words[0])
		op = words[1]
		val = float(words[-1])
		if s_output_type == 'obs-1q':
			q_index1 = int(words[2]) - 1
			# data files are storing 1-based indices because of iTensor, while we use 0-based indices
			q_indices = (q_index1,)
		elif s_output_type == 'obs-2q':
			q_index1 = int(words[2]) - 1
			# data files are storing 1-based indices because of iTensor, while we use 0-based indices
			q_index2 = int(words[3]) - 1
			q_indices = (q_index1, q_index2)
		elif s_output_type == 'global':
			q_indices = ()
		else:
			raise Exception(f"Unknown output type {s_output_type}.")
		# The result dictionary is indexed by a tuple, first entry is a name, second entry is
		# a tuple of qubit indices - 0 indices for the global data, 1 for 1Q observables, 2 for 2Q.
		obs_data = result.get((op.lower(), q_indices), None)
		# obs_data is a tuple, first entry is a list of times, second entry holds the values.
		if obs_data is None:
			obs_data = (list(), list())
			result[(op.lower(), q_indices)] = obs_data
		# TODO: optimize the list appends
		obs_data[0].append(t)
		obs_data[1].append(val)

	@staticmethod
	# checks if the value is int (for cleaner code)
	def _is_int(value):
		return isinstance(value, int)

	@staticmethod
	# checks if the value is a float (for cleaner code)
	def _is_float(value):
		# in python terms the value <4> is not float type, in the simulator context float can also be a python int:
		return isinstance(value, (float, int))

	@staticmethod
	# returns the number of qubits based on the given parameters, returns -1 if found an error
	def _get_number_of_qubits(parameters: Dict) -> int:
		if "N" in parameters:
			if LindbladMPOSolver._is_int(parameters["N"]):
				return parameters["N"]
		return -1

	def _virtual_verify_parameters(self, ignore_params: Optional[list] = None) -> str:
		"""An overridable function that verifies the parameters by calling verify_parameters().

		Args:
			ignore_params: A list with parameter names that this solver does not recognize, but
				should be ignored in the verification (so that an error message for unknown parameters
				is not issued). This is useful for derived classes.
		Returns:
			A detailed error message if parameters arguments are not in the correct format (which
				is stated in the spec of the simulator). Otherwise, returns "" (checks passed).
		"""
		return LindbladMPOSolver.verify_parameters(self.parameters, ignore_params)

	@staticmethod
	def verify_parameters(parameters: dict, ignore_params: Optional[list] = None) -> str:
		"""Returns a detailed Error message if parameters are not in the correct format.

		Args:
			parameters: A dictionary of solver parameters.
			ignore_params: A list with parameter names that this solver does not recognize, but
				should be ignored in the verification (so that an error message for unknown parameters
				is not issued). This parameter is mostly useful for derived subclasses.
		Returns:
			A detailed error message if parameters are not in the correct format.
			Otherwise, returns "" (checks passed).
		"""
		check_msg = ""
		if parameters is None:
			check_msg += "Error 100: The `parameters` dictionary must be assigned\n"
			return check_msg
		if ("N" not in parameters) or ("t_final" not in parameters) or ("tau" not in parameters):
			check_msg += "Error 110: N, t_final and tau must be defined as they do not have default " \
						 "values\n"
			return check_msg
		for key in dict.keys(parameters):
			if isinstance(parameters[key], str) and "" == parameters[key]:  # ignore empty entrances/space holders <"">
				continue
			flag_continue = False

			if key == "N":
				if not LindbladMPOSolver._is_int(parameters[key]):
					check_msg += "Error 120: " + key + " should be an integer\n"
					continue
				if parameters[key] <= 0:
					check_msg += "Error 130: " + key + " should be bigger/equal to 1 (integer)\n"
					continue
			elif key == "t_init" or key == "t_final" or key == "tau":
				if not LindbladMPOSolver._is_float(parameters[key]):
					check_msg += "Error 140: " + key + " is not a float\n"
					continue
				if key != "t_init" and parameters[key] <= 0:
					check_msg += "Error 150: " + key + " must be larger than 0\n"
					continue
				if key == "t_init" and parameters[key] > parameters["t_final"]:
					check_msg += "Error 151: " + key + " must be equal or smaller than t_final\n"
					continue
			elif (key == "l_x") or (key == "l_y"):
				if not LindbladMPOSolver._is_int(parameters[key]):
					check_msg += "Error 160: " + key + " should be an integer\n"
					continue
				if parameters[key] < 0:
					check_msg += "Error 170: " + key + " should be equal or larger than 1 (integer)\n"
					continue
			elif key == "output_step" or key == "force_rho_hermitian_step":
				if not LindbladMPOSolver._is_int(parameters[key]):
					check_msg += "Error 180: " + key + " should be an integer\n"
					continue
				if parameters[key] < 0:
					check_msg += "Error 190: " + key + " should be bigger/equal to 0 (integer)\n"
					continue
			elif (key == "h_x") or (key == "h_y") or (key == "h_z") or \
					(key == "g_0") or (key == "g_1") or (key == "g_2"):
				if LindbladMPOSolver._is_float(parameters[key]):
					continue
				number_of_qubits = LindbladMPOSolver._get_number_of_qubits(parameters)
				if number_of_qubits == -1:
					check_msg += "Error 200: " + key + " could not be validated because 'N' " \
													   "(or alternatively l_x, l_y) are not " \
													   "defined properly\n "
					continue
				if isinstance(parameters[key], list):
					if len(parameters[key]) != number_of_qubits:
						check_msg += "Error 210: " + key + " is not a float / N-length list / " \
														   "numpy array (of floats)\n"
						continue
					for element in parameters[key]:
						if not LindbladMPOSolver._is_float(element):
							check_msg += "Error 220: " + key + "is not a float / N-length list " \
															   "/ numpy array (of floats)\n "
							flag_continue = True
							break
					if flag_continue:
						continue
				elif isinstance(parameters[key], np.ndarray):
					if (str((parameters[key]).dtype).find("int") == -1) and (
							str((parameters[key]).dtype).find("float") == -1):
						check_msg += "Error 230: " + key + " is not a float / N-length list / " \
														   "numpy array (of floats)\n"
						continue
					if parameters[key].size == 1:
						continue
					if (parameters[key].shape[0] != number_of_qubits) or\
							(parameters[key].shape[0] != parameters[key].size):
						check_msg += "Error 240: " + key + " is not a float / N-length list / " \
														   "numpy array (of floats)\n"
						continue
				else:
					check_msg += "Error 250: " + key + " is not a float / N-length list / numpy " \
													   "array (of floats)\n"
					continue
			elif (key == "J_z") or (key == "J"):
				if LindbladMPOSolver._is_float(parameters[key]):
					continue
				number_of_qubits = LindbladMPOSolver._get_number_of_qubits(parameters)
				if number_of_qubits == -1:
					check_msg += "Error 260: " + key + " could not be validated because 'N' " \
													   "(or alternatively l_x, l_y) are not " \
													   "defined properly\n"
					continue
				if isinstance(parameters[key], list):
					if len(parameters[key]) != number_of_qubits:
						check_msg += "Error 270: " + key +\
									 " should be a constant, or a square matrix" \
									 " (nested lists/np.array) of N^2 floats\n "
						continue
					for lst in parameters[key]:
						if not isinstance(lst, list):
							check_msg += "Error 280: " + key + "should be a constant, or a square " \
															   "matrix (nested lists/np.array) of " \
															   "floats with a size N^2\n "
							flag_continue = True
							break
						if len(lst) != number_of_qubits:
							check_msg += "Error 290: " + key +\
										 "should be a constant, or a square matrix (nested " \
										 "lists/np.array) with N^2 floats\n"
							flag_continue = True
							break
						for val in lst:
							if not LindbladMPOSolver._is_float(val):
								check_msg += "Error 300: " + key +\
											 "should be a constant, or a square matrix (nested " \
											 "lists/np.array) in the size of number_of_qubits^2 " \
											 "of floats\n"
								flag_continue = True
								break
						if flag_continue:
							break
					if flag_continue:
						continue
				elif isinstance(parameters[key], np.ndarray):
					if (str((parameters[key]).dtype).find("int") == -1) and (
							str((parameters[key]).dtype).find("float") == -1):
						check_msg += "Error 310: " + key +\
									 "should be a constant, or a square matrix (nested " \
									 "lists/np.array) in the size of number_of_qubits^2 of " \
									 "floats\n"
						continue
					if parameters[key].size == 1:
						continue
					if parameters[key].shape[0] != number_of_qubits:
						check_msg += "Error 320: " + key +\
									 "should be a constant, or a square matrix (nested " \
									 "lists/np.array) in the size of number_of_qubits^2 of " \
									 "floats\n"
						continue
					if parameters[key].shape[0] ** 2 != parameters[key].size:
						check_msg += "Error 330: " + key +\
									 "should be a constant, or a square matrix (nested " \
									 "lists/np.array) in the size of number_of_qubits^2 of " \
									 "floats\n"
						continue
				else:
					check_msg += "Error 340: " + key +\
								 " should be a constant, or a square matrix (nested " \
								 "list/np.array) in the size of number_of_qubits^2 of floats\n"
					continue
			elif key == "init_pauli_state":
				if not isinstance(parameters[key], str) and not isinstance(parameters[key], list):
					check_msg += "Error 350: " + key + " must not be a string or a list of strings\n"
					continue
				init_list = [parameters[key]] if isinstance(parameters[key], str) else parameters[key]
				for s_init in init_list:
					if not isinstance(s_init, str):
						check_msg += "Error 360: each member of " + key + " must be a string\n"
						continue
					allowed_init = ['+x', '-x', '+y', '-y', '+z', '-z']
					if s_init.lower() not in allowed_init:
						check_msg += "Error 370: " + key + " can only be one of: +x,-x,+y,-y,+z, z\n"
						continue
			elif ((key == "b_periodic_x") or (key == "b_periodic_y") or (key == "b_force_rho_trace") or
				  (key == "b_unique_id") or (key == "b_save_final_state") or
				  (key == "b_initial_rho_compression")):
				if not isinstance(parameters[key], bool):
					check_msg += "Error 390: " + key + " should be a boolean True or False\n"
					continue
			elif key == "trotter_order":
				if not LindbladMPOSolver._is_int(parameters[key]):
					check_msg += "Error 400: " + key + " should be 2, 3 or 4\n"
					continue
				if (parameters[key] != 2) and (parameters[key] != 3) and (parameters[key] != 4):
					check_msg += "Error 401: " + key + " should be 2, 3 or 4\n"
					continue
			elif key == "max_dim_rho":  # int
				if not LindbladMPOSolver._is_int(parameters[key]) or parameters[key] < 0:
					check_msg += "Error 410: " + key + " must be a non-negative integer\n"
					continue
			elif (key == "cut_off") or (key == "cut_off_rho"):
				if not LindbladMPOSolver._is_float(parameters[key]):
					check_msg += "Error 420: " + key + " is not a float\n"
					continue
			elif key == "metadata":
				if not isinstance(parameters[key], str):
					check_msg += "Error 422: " + key + " is not a string\n"
					continue
				if '\n' in parameters[key]:
					check_msg += "Error 423: " "The metadata string cannot contain the new line "\
								 "character code ('\\n'). Please reformat the string\n"
					continue
			elif key == "load_files_prefix" or key == "output_files_prefix":
				if not isinstance(parameters[key], str):
					check_msg += "Error 425: " + key + " is not a string\n"
					continue
			elif key == "1q_components":
				x_c = 0
				y_c = 0
				z_c = 0
				if not isinstance(parameters[key], list):
					check_msg += "Error 430: " + key + " should be a list of size 1,2,3 with x,y,z\n"
					continue
				if len(parameters[key]) > 3:
					check_msg += "Error 440: " + key + " should be a list of size 1,2,3 with x,y,z\n"
					continue
				for val in parameters[key]:
					if not isinstance(val, str):
						check_msg += "Error 441: " + key + " only takes x,y,z (or a subset)\n"
						flag_continue = True
						break
					val = str.lower(val)
					if val == "x":
						x_c += 1
					elif val == "y":
						y_c += 1
					elif val == "z":
						z_c += 1
					else:
						check_msg += "Error 450: " + key + " only takes x,y,z (or a subset)\n"
						flag_continue = True
						break
				if flag_continue:
					continue
				if (x_c > 1) or (y_c > 1) or (z_c > 1):
					check_msg += "Error 460: " + key + " only takes x,y,z (or a subset)\n"
					continue
			elif key == "1q_indices":
				if parameters[key] != "":
					if not isinstance(parameters[key], list):
						check_msg += "Error 470: " + key + " should be an integer list (1,2,3,4..)\n"
						continue
					number_of_qubits = LindbladMPOSolver._get_number_of_qubits(parameters)
					if number_of_qubits == -1:
						check_msg += "Error 480: " + key + "could not be validated because 'N'" \
														   " (or alternatively l_x," \
														   " l_y) are not defined properly\n "
						continue
					for element in parameters[key]:
						if not LindbladMPOSolver._is_int(element):
							check_msg += "Error 490: " + key + " should be an integer list (1,2,3,4..)\n"
							flag_continue = True
							break
						if element >= number_of_qubits:
							check_msg += "Error 500: " + key + " should be an integer list listing " \
															   "qubits, therefore integers in the " \
															   "range 0 to N-1\n"
							flag_continue = True
							break
					if flag_continue:
						continue
					if len(parameters[key]) > number_of_qubits:
						check_msg += "Error 510: " + key + " 's length should be equal/smaller than " \
														   "the amount of qubits\n "
						continue
					if not len(set(parameters[key])) == len(parameters[key]):
						check_msg += "Error 520: " + key + " 's List does not contain unique elements"
						continue
			elif key == "2q_components":
				if not isinstance(parameters[key], list):
					check_msg += "Error 530: " + key + "only receives xx,yy,zz,xy,xz,yz (or a subset) " \
													   "as a strings list\n"
					continue
				if len(parameters[key]) > 6:
					check_msg += "Error 540: " + key + " only receives xx,yy,zz,xy,xz,yz (or a subset)\n"
					continue
				check_me = [0, 0, 0, 0, 0, 0]
				for val in parameters[key]:
					val = str.lower(val)
					if val == "xx":
						check_me[0] += 1
					elif val == "yy":
						check_me[1] += 1
					elif val == "zz":
						check_me[2] += 1
					elif (val == "xy") or (val == "yx"):
						check_me[3] += 1
					elif (val == "xz") or (val == "zx"):
						check_me[4] += 1
					elif (val == "yz") or (val == "zy"):
						check_me[5] += 1
					else:
						check_msg += "Error 550: " + key + " only accepts string from xx, yy, zz, xy, " \
														   "xz, yz (or a permutation thereof)\n"
						flag_continue = True
						break
				if flag_continue:
					continue
				for check_val in check_me:
					if check_val > 1:
						check_msg += "Error 550: " + key + " only accepts string from xx, yy, zz, xy, " \
														   "xz, yz (or a permutation thereof)\n"
						flag_continue = True
						break
				if flag_continue:
					continue
			elif key == "2q_indices" or key == "init_graph_state":  # expecting an integer tuples list
				if not isinstance(parameters[key], list):
					check_msg += "Error 570: " + key + " should be an list of tuples of size 2," \
													   " containing integers\n"
					continue
				number_of_qubits = LindbladMPOSolver._get_number_of_qubits(parameters)
				if number_of_qubits == -1:
					check_msg += "Error 580: " + key + " could not be validated because 'N' " \
													   "(or alternatively l_x, " \
													   "l_y) are not defined properly\n"
					continue
				for tup in parameters[key]:
					if not isinstance(tup, tuple):
						check_msg += "Error 590: " + key + " should be an list of tuples of size 2, " \
														   "containing integers\n "
						flag_continue = True
						break
					if ((not LindbladMPOSolver._is_int(tup[0])) or
							(not LindbladMPOSolver._is_int(tup[1])) or (len(tup) != 2)):
						check_msg += "Error 600: " + key + " should be an list of tuples of size 2, " \
														   "containing integers\n "
						flag_continue = True
						break
					if (tup[0] >= number_of_qubits) or (tup[1] >= number_of_qubits):
						check_msg += "Error 610: " + key + " should be an list of tuples of size 2, " \
														   "containing integers equal/smaller than " \
														   "the total number of qubits\n "
						flag_continue = True
						break
				if flag_continue:
					continue
				if len(parameters[key]) > number_of_qubits ** 2:
					check_msg += "Error 620: " + key + " 's length should be smaller than N^2\n"
					continue
				if not len(set(parameters[key])) == len(parameters[key]):
					check_msg += "Error 630: " + key + " 's List does not contains all unique elements"
					continue
			elif ignore_params is None or key not in ignore_params:
				check_msg += "Error: unknown parameter key passed: " + key + "\n"
		# End of: "for key in dict.keys(parameters)"

		# More cross-parameter checks:
		if ("t_final" in parameters) and ("tau" in parameters):
			if (LindbladMPOSolver._is_float(parameters["tau"])) and\
					(LindbladMPOSolver._is_float(parameters["t_final"])):
				if (parameters["tau"] > 0) and (parameters["t_final"] > 0):
					if parameters["tau"] > parameters["t_final"]:
						check_msg += "Error 640: t_final (total time) is smaller than tau (time step " \
									 "for time evolution)\n "
						# TODO validate total time as t_final - t_init
						# TODO validate force_rho_hermitian_step
					elif "output_step" in parameters:
						if LindbladMPOSolver._is_int(parameters["output_step"]):
							if parameters["output_step"] > 0:
								if parameters["output_step"] * parameters["tau"] > parameters["t_final"]:
									check_msg += "Error 650: output_step multiplied by tau is larger " \
												 "than t_final (output_step in units of tau, times " \
												 "tau is larger than the simulation time)\n "
		return check_msg
