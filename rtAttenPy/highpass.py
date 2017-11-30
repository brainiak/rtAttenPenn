import numpy as np

# TODO: Verify index bug in hp_convkernel
def hp_convkernel(hp_mask_size, sigma):
    xs = np.array([i - hp_mask_size for i in range(hp_mask_size * 2 + 1)])
    xs = np.exp(-0.5 * xs * xs / (sigma * sigma))
    return xs

# result = rtAttenPy.highpass(a['a']['data'][0][0], 28)
# TODO: This is an ultra-bad implementation (e.g., column-major when
# it should be row-major; not parallelizing; not using scipy convolve)
def highpass(data, sigma):
    hp_mask_size = sigma * 3
    data = np.transpose(data)
    ncol, nrow = data.shape
    print(data.shape)

    result = np.empty_like(data)

    # NOTE: MATLAB data is column-major order

    # Number of time points (rows)
    nt = nrow

    # Number of voxels (columns)
    nv = ncol

    # Get convolution kernel
    hp_exp = hp_convkernel(hp_mask_size, sigma)

    # Loop over columns first, then rows
    for v in range(nv):
        print('Voxel %d of %d' % (v + 1, nv))
        done_c0 = 0
        c0 = 0
        for t in range(nt):
            A = B = C = D = N = 0
            tt_left = max(t - hp_mask_size, 0)
            tt_right = min(t + hp_mask_size, nt - 1)

            for tt in range(tt_left, tt_right + 1):
                dt = tt - t
                w = hp_exp[dt + hp_mask_size]
                A += w * dt
                B += w * data[v][tt]
                C += w * dt * dt
                D += w * dt * data[v][tt]
                N += w

            tmpdenom = C * N - A * A

            if tmpdenom != 0:
                c = (B * C - A * D) / tmpdenom
                if done_c0 == 0:
                    c0 = 0
                    done_c0 = 1

                result[v][t] = c0 + data[v][t] - c
            else:
                result[v][t] = data[v][t]

    return result
