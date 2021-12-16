# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Routines for basic plotting of simulation results, with both general and more specialized functions.
"""

from typing import Optional, Tuple, List, Union

from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt
import numpy as np
from lindbladmpo.LindbladMPOSolver import LindbladMPOSolver


LINDBLADMPO_TEX_LABELS =\
{
	'tr_rho': '{\\rm tr}\\rho',
	's_2': 'S_2',
	'osee_center': 'OSEE_{\\rm center}',
	'max_bond_dim': '{\\rm max bond-dim}',
	'duration_ms': '{\\rm duration(ms)}',
}
"""Labels in LaTex format for global output data, indexed by their data file entries.
	Note that key entries here are lower-case."""


LINDBLADMPO_LINE_STYLES = ['-', '--', ':', '-.']
"""Line styles for curves plotted using matplotlib"""


def prepare_time_data(parameters: dict, n_t_ticks = 10, t_ticks_round = 3)\
		-> (np.ndarray, np.ndarray, np.ndarray, int):
	"""
	Prepare the time variables used in plotting the results from one simulation.

	Args:
		parameters: A dictionary from which the basic time parameters are taken.
		n_t_ticks: The number of labeled major tick marks to generate for the time axis.
		t_ticks_round: The number of digits to round time axis tick labels to.

	Returns:
		A tuple with the following four entries:
			t_eval: An array of the times for which the solver parameters indicate output is to
				be evaluated for (based on the `t_init`, `t_final`, and `tau` parameters.
			t_tick_indices: The indices of the time axis tick marks.
			t_tick_labels: The formatted labels of the time axis tick marks.
			n_t_steps: The number of time steps
	"""
	tau = parameters['tau']
	t_final = parameters['t_final']
	t_init = parameters.get('t_init', 0.)
	# output_step = parameters.get('output_step', 1)
	# TODO handle output_step
	n_t_steps = int((t_final - t_init) / (tau * 1)) + 1
	t_tick_indices = np.arange(0, n_t_steps, int(n_t_steps / n_t_ticks))
	t_eval = np.arange(t_init, t_final, tau)
	if t_final not in t_eval:
		t_eval = np.concatenate((t_eval, [t_final]))
	t_tick_labels = np.round(t_init + t_tick_indices * tau, t_ticks_round)
	return t_eval, t_tick_indices, t_tick_labels, n_t_steps


def prepare_curve_data(result: dict, s_output_type: str, s_obs_name: str,
					   q_indices: Union[Tuple, Tuple[int]]) -> ((list, list), str):
	"""
	Prepare the data used for plotting one curve of simulation observables.

	Args:
		result: A dictionary from which the observables are taken.
		s_output_type: The type of output, used a key into the result dict, and also in formatting
			the descriptive tex label of the data.
		s_obs_name: The name of the specific observable, used a key into the relevant observables dict,
			and also in formatting the descriptive tex label of the data.
		q_indices: A tuple with the indices of the qubits identifying the observable to plot, or
			an empty tuple if the observable is a global one.

	Returns:
		A tuple with the following two entries:
			obs_data: A tuple of two lists, the first being the time points, the second being the data.
			s_tex_label: A formatted tex label for the data.
	"""
	obs_dict = result[s_output_type]
	obs_data = None
	s_tex_label = ""
	s_obs_name = s_obs_name.lower()
	if obs_dict is not None:
		obs_data = obs_dict.get((s_obs_name, q_indices))
		if s_output_type == 'obs-1q':
			s_tex_label = f"\\sigma^{s_obs_name}_{{{q_indices[0]}}}"
		elif s_output_type == 'obs-2q':
			s_tex_label =\
				f"\\sigma^{s_obs_name[0]}_{{{q_indices[0]}}} \\sigma^{s_obs_name[1]}_{{{q_indices[1]}}}"
		elif s_output_type == 'global':
			s_tex_label = LINDBLADMPO_TEX_LABELS[s_obs_name]
	return obs_data, s_tex_label


def prepare_2q_correlation_data(result: dict, s_obs_name: str, q_indices: Tuple[int])\
		-> ((list, list), str):
	"""
	Prepare the data used for plotting one curve of a two-qubit connected correlation function.
	The connected correlation is defined as a 2Q observable from which the product of the two
	corresponding 1Q observables is subtracted.

	Args:
		result: A dictionary from which the observables are taken.
		s_obs_name: The name of the specific observable, used a key into the relevant observables dict,
			and also in formatting the descriptive tex label of the data.
		q_indices: A tuple with the indices of the qubits identifying the correlation function.

	Returns:
		A tuple with the following two entries:
			obs_data: A tuple of two lists, the first being the time points, the second being the data.
			s_tex_label: A formatted tex label for the data - note that this string does not indicate
				that the data is of 2Q connected correlation (the subtraction of the 1Q product).
	"""
	obs_1q_dict = result['obs-1q']
	obs_2q_dict = result['obs-2q']
	obs_data = None
	s_tex_label = ""
	s_obs_name = s_obs_name.lower()
	# Below we verify that all required 1Q and 2Q observables have complete data available.
	if obs_1q_dict is not None and obs_2q_dict is not None:
		obs_0 = obs_1q_dict.get((s_obs_name[0], (q_indices[0],)))
		obs_1 = obs_1q_dict.get((s_obs_name[1], (q_indices[1],)))
		obs_2 = obs_2q_dict.get((s_obs_name, q_indices))
		if obs_0 is not None and obs_1 is not None and obs_2 is not None and\
				len(obs_0[0]) == len(obs_1[0]) and len(obs_0[0]) == len(obs_2[0]):
			# The data all comes from one simulation, so we can safely assume that the observation
			# times are identical, if they are equal in number. Verifying the time array lengths
			# will avoid crashes due to interrupted simulations with incomplete data files.
			obs_data = (obs_0[0], (np.asarray(obs_2[1]) -
						np.asarray(obs_0[1]) * np.asarray(obs_1[1])).tolist())
			s_tex_label = f"\\sigma^{s_obs_name[0]}_{{{q_indices[0]}}} "\
				f"\\sigma^{s_obs_name[1]}_{{{q_indices[1]}}}"
	return obs_data, s_tex_label


def prepare_2q_correlation_matrix(result: dict, s_obs_name: str, t: float, n_qubits: int)\
		-> (np.ndarray, str):
	"""
	Prepare the data used for plotting the matrix of connected correlation values of one type for all.
	qubits. The connected correlation is defined as a 2Q observable from which the product of the two
	corresponding 1Q observables is subtracted.

	Args:
		result: A dictionary from which the observables are taken.
		s_obs_name: The name of the specific observable, used a key into the relevant observables dict,
			and also in formatting the descriptive tex label of the data.
		t: The simulation time for which the data is to be calculated.
		n_qubits: The number of qubits in the simulation.

	Returns:
		A tuple with the following two entries:
			obs_data: A matrix with the connected correlation function of all qubits at time `t`.
			s_tex_label: A formatted tex label for the data - note that this string does not indicate
				that the data is of 2Q connected correlation (the subtraction of the 1Q product).
	"""
	obs_1q_dict = result['obs-1q']
	obs_2q_dict = result['obs-2q']
	obs_data = np.full(shape = (n_qubits, n_qubits), dtype = float, fill_value = np.nan)
	s_obs_name = s_obs_name.lower()
	r_qubits = range(n_qubits)
	# Below we verify that all required 1Q and 2Q observables have complete data available.
	if obs_1q_dict is not None and obs_2q_dict is not None:
		for i in r_qubits:
			for j in r_qubits:
				if i == j:
					continue
				obs_0 = obs_1q_dict.get((s_obs_name[0], (i,)))
				obs_1 = obs_1q_dict.get((s_obs_name[1], (j,)))
				obs_2 = obs_2q_dict.get((s_obs_name, (i, j)))
				if obs_0 is not None and obs_1 is not None and obs_2 is not None and\
						len(obs_0[0]) == len(obs_1[0]) and len(obs_0[0]) == len(obs_2[0]):
					# The data all comes from one simulation, so we can safely assume that the time
					# arrays are identical, if they are equal in number. Verifying the time array lengths
					# will avoid crashes due to interrupted simulations with incomplete data files.
					try:
						t_index = obs_0[0].index(t)
						obs_data[i, j] = obs_2[1][t_index] - obs_0[1][t_index] * obs_1[1][t_index]
					except ValueError:
						pass
	s_tex_label = f"\\sigma^{s_obs_name[0]}_{{i}}\\sigma^{s_obs_name[1]}_{{j}}"
	return obs_data, s_tex_label


def plot_curves(obs_data_list: List[Tuple[List]], tex_labels: List[str], s_title = '',
				ax = None, fontsize = 16):
	"""
	Plot multiple curves of simulation observables.

	Args:
		obs_data_list: A list of obs_data tuples of lists, from which the plotted data is taken.
		tex_labels: A list of descriptive tex label corresponding to the data.
		s_title: An optional plot title.
		ax: An optional axis object. If None, a new figure is created.
		fontsize: The fontsize to use in the figure.

	Returns:
		An axis object (either the one passed as an argument, or a newly created one).
	"""
	if ax is None:
		_, ax = plt.subplots(figsize = (14, 9))
	plt.rcParams.update({'font.size': fontsize})
	for i_curve, obs_data in enumerate(obs_data_list):
		ax.plot(obs_data[0], obs_data[1], label = tex_labels[i_curve],
				 linestyle = LINDBLADMPO_LINE_STYLES[i_curve % 4], linewidth = 3)
	ax.legend(fontsize = fontsize)
	ax.set_xlabel('$t$', fontsize = fontsize)
	if s_title != '':
		ax.set_title(s_title)
	return ax


def prepare_1q_space_time_data(parameters: dict, result: dict, s_obs_name: str,
							   qubits: Optional[Union[List[int], np.ndarray]] = None,
							   n_t_ticks = 10, t_ticks_round = 3)\
		-> (np.ndarray, np.ndarray, np.ndarray, np.ndarray):
	_, t_tick_indices, t_tick_labels, n_t_steps = prepare_time_data(parameters, n_t_ticks, t_ticks_round)
	if qubits is None:
		N = parameters['N']
		qubits = np.arange(N)
		# Generate a default full 1Q matrix
	n_qubits = len(qubits)
	data = np.full(shape = (n_qubits, n_t_steps), dtype = float, fill_value = np.nan)
	for i_q, qubit in enumerate(qubits):
		obs_data, s_tex_label = prepare_curve_data(result, 'obs-1q', s_obs_name, (qubit,))
		# TODO add t_eval verification against obs_data[1]
		data[i_q, :] = obs_data[1]
	return data, t_tick_indices, t_tick_labels, qubits


def prepare_2q_matrix_data(parameters: dict, result: dict, s_obs_name: str, t: float)\
		-> (np.ndarray, np.ndarray):
	N = parameters['N']
	qubits = np.arange(N)
	n_qubits = len(qubits)
	data, s_tex_label = prepare_2q_correlation_matrix(result, s_obs_name, t, n_qubits)
	return data, qubits


def plot_1q_space_time(data, s_obs_name: str, qubits, t_tick_indices, t_tick_labels,
					   ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	s_obs_name = s_obs_name.lower()
	if ax is None:
		_, ax = plt.subplots(figsize = (14, 9))
	plt.rcParams.update({'font.size': fontsize})
	im = ax.imshow(data, interpolation = 'none', aspect = 'auto')
	divider = make_axes_locatable(ax)
	cax = divider.append_axes('right', size = '5%', pad = 0.05)
	plt.colorbar(im, cax = cax)
	# plt.colorbar(im)
	ax.set_xlabel('$t$', fontsize = fontsize)
	ax.set_xticks(t_tick_indices)
	ax.set_xticklabels(t_tick_labels, fontsize = fontsize)
	ax.set_yticks(qubits)
	ax.set_yticklabels(qubits, fontsize = fontsize)
	ax.set_ylabel('$j$', fontsize = fontsize)
	s_title = f'$\\langle\\sigma^{s_obs_name}(t)\\rangle$'
	ax.set_title(s_title)
	s_file_label = f"sigma_{s_obs_name}.st"
	_save_fig(b_save_figures, s_file_prefix, s_file_label)


def plot_2q_correlation_matrix(data, s_obs_name: str, t: float, qubits,
							   ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	s_obs_name = s_obs_name.lower()
	if ax is None:
		_, ax = plt.subplots(figsize = (14, 9))
	plt.rcParams.update({'font.size': fontsize})
	im = ax.imshow(data, interpolation = 'none', aspect = 'auto')
	divider = make_axes_locatable(ax)
	cax = divider.append_axes('right', size = '5%', pad = 0.05)
	plt.colorbar(im, cax = cax)
	# plt.colorbar(im)
	ax.set_xlabel('$i$', fontsize = fontsize)
	ax.set_xticks(qubits)
	ax.set_xticklabels(qubits, fontsize = fontsize)
	ax.set_yticks(qubits)
	ax.set_yticklabels(qubits, fontsize = fontsize)
	ax.set_ylabel('$j$', fontsize = fontsize)
	s_tex_label = f"\\sigma^{s_obs_name[0]}_{{i}}\\sigma^{s_obs_name[1]}_{{j}}"
	s_title = f'$\\langle{s_tex_label}(t={t})\\rangle_{{c}}$'
	ax.set_title(s_title)
	s_file_label = f"sigma_{s_obs_name[0]}.sigma_{s_obs_name[1]}.c.t={t}"
	_save_fig(b_save_figures, s_file_prefix, s_file_label)


def plot_full_1q_space_time(parameters: dict, result: dict, s_obs_name: str,
							ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	data, t_tick_indices, t_tick_labels, qubits =\
		prepare_1q_space_time_data(parameters, result, s_obs_name)
	plot_1q_space_time(data, s_obs_name, qubits, t_tick_indices, t_tick_labels,
					   ax, fontsize, b_save_figures, s_file_prefix)


def plot_full_2q_correlation_matrix(parameters: dict, result: dict, s_obs_name: str, t: float,
									ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	data, qubits = prepare_2q_matrix_data(parameters, result, s_obs_name, t)
	plot_2q_correlation_matrix(data, s_obs_name, t, qubits,
							   ax, fontsize, b_save_figures, s_file_prefix)


def plot_1q_obs_curves(parameters: dict, result: dict, s_obs_name: str,
					   qubits: Optional[List[int]] = None,
					   ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	obs_data_list = []
	tex_labels = []
	s_obs_name = s_obs_name.lower()
	for qubit in qubits:
		obs_data, s_tex_label = prepare_curve_data(result, 'obs-1q', s_obs_name, (qubit,))
		obs_data_list.append(obs_data)
		tex_labels.append(f'$\\langle{s_tex_label}(t)\\rangle$')
	s_title = f'$\\langle\\sigma^{s_obs_name}_j(t)\\rangle$'
	ax = plot_curves(obs_data_list, tex_labels, s_title, ax, fontsize)
	_, t_tick_indices, t_tick_labels, _ = prepare_time_data(parameters)
	# ax.set_xticks(t_tick_indices)
	ax.set_xticks(t_tick_labels)
	ax.set_xticklabels(t_tick_labels, fontsize = fontsize)
	s_file_label = f"sigma_{s_obs_name}"
	_save_fig(b_save_figures, s_file_prefix, s_file_label)


def plot_2q_obs_curves(parameters: dict, result: dict, s_obs_name: str,
					   qubit_pairs: Optional[List[Tuple[int, int]]] = None,
					   ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	obs_data_list = []
	tex_labels = []
	s_obs_name = s_obs_name.lower()
	for q_pair in qubit_pairs:
		obs_data, s_tex_label = prepare_curve_data(result, 'obs-2q', s_obs_name, q_pair)
		if obs_data is not None:
			obs_data_list.append(obs_data)
			tex_labels.append(f'$\\langle{s_tex_label}(t)\\rangle$')
	s_title = f'$\\langle\\sigma^{s_obs_name[0]}_i\\sigma^{s_obs_name[1]}_j(t)\\rangle$'
	ax = plot_curves(obs_data_list, tex_labels, s_title, ax, fontsize)
	_, t_tick_indices, t_tick_labels, _ = prepare_time_data(parameters)
	# ax.set_xticks(t_tick_indices)
	ax.set_xticks(t_tick_labels)
	ax.set_xticklabels(t_tick_labels, fontsize = fontsize)
	s_file_label = f"sigma_{s_obs_name[0]}.sigma_{s_obs_name[1]}"
	_save_fig(b_save_figures, s_file_prefix, s_file_label)


def plot_2q_correlation_curves(parameters: dict, result: dict, s_obs_name: str,
							   qubit_pairs: Optional[List[Tuple[int, int]]] = None,
							   ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	obs_data_list = []
	tex_labels = []
	s_obs_name = s_obs_name.lower()
	for q_pair in qubit_pairs:
		obs_data, s_tex_label = prepare_2q_correlation_data(result, s_obs_name, q_pair)
		if obs_data is not None:
			obs_data_list.append(obs_data)
			tex_labels.append(f'$\\langle{s_tex_label}(t)\\rangle_{{c}}$')
	s_title = f'$\\langle\\sigma^{s_obs_name[0]}_i\\sigma^{s_obs_name[1]}_j(t)\\rangle_{{c}}$'
	ax = plot_curves(obs_data_list, tex_labels, s_title, ax, fontsize)
	_, t_tick_indices, t_tick_labels, _ = prepare_time_data(parameters)
	# ax.set_xticks(t_tick_indices)
	ax.set_xticks(t_tick_labels)
	ax.set_xticklabels(t_tick_labels, fontsize = fontsize)
	s_file_label = f"sigma_{s_obs_name[0]}.sigma_{s_obs_name[1]}.c"
	_save_fig(b_save_figures, s_file_prefix, s_file_label)


def plot_global_obs_curve(parameters: dict, result: dict, s_obs_name: str,
						  ax = None, fontsize = 16, b_save_figures = True, s_file_prefix = ''):
	s_obs_name = s_obs_name.lower()
	obs_data, s_tex_label = prepare_curve_data(result, 'global', s_obs_name, ())
	s_title = f'${s_tex_label}(t)$'
	ax = plot_curves([obs_data], [s_title], s_title, ax, fontsize)
	_, t_tick_indices, t_tick_labels, _ = prepare_time_data(parameters)
	# ax.set_xticks(t_tick_indices)
	ax.set_xticks(t_tick_labels)
	ax.set_xticklabels(t_tick_labels, fontsize = fontsize)
	s_file_label = s_obs_name
	_save_fig(b_save_figures, s_file_prefix, s_file_label)


def _save_fig(b_save_figures, s_file_prefix, s_file_label):
	if b_save_figures:
		if s_file_prefix != '':
			s_file_label = '.' + s_file_label
		plt.savefig(s_file_prefix + s_file_label + '.png')
