import numpy as np


def stable_softmax(scores):
    """Numerically stable softmax along last axis."""
    scores = np.asarray(scores, dtype=np.float64)
    shifted = scores - np.max(scores, axis=-1, keepdims=True)
    exp_scores = np.exp(shifted)
    sum_exp = np.sum(exp_scores, axis=-1, keepdims=True)
    # Avoid division by zero if all are masked
    sum_exp = np.where(sum_exp == 0, 1.0, sum_exp)
    return exp_scores / sum_exp


def attention_scores(queries, keys):
    """Calculates scaled dot-product attention scores (Q @ K.T) / sqrt(d_k)."""
    queries = np.asarray(queries, dtype=np.float64)
    keys = np.asarray(keys, dtype=np.float64)
    d_k = queries.shape[-1]
    raw_scores = np.matmul(queries, keys.swapaxes(-1, -2))
    return raw_scores / np.sqrt(d_k)


def scaled_dot_product_attention(queries, keys, values, allowed=None):
    """Computes scaled dot-product attention with optional mask."""
    queries = np.asarray(queries, dtype=np.float64)
    keys = np.asarray(keys, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)

    scores = attention_scores(queries, keys)

    if allowed is not None:
        allowed = np.asarray(allowed, dtype=bool)
        # Mask out disallowed entries with large negative value
        scores = np.where(allowed, scores, -1e9)

    weights = stable_softmax(scores)

    if allowed is not None:
        weights = np.where(allowed, weights, 0.0)
        sum_w = weights.sum(axis=-1, keepdims=True)
        sum_w = np.where(sum_w == 0, 1.0, sum_w)
        weights = weights / sum_w

    attended = np.matmul(weights, values)
    return attended, weights


if __name__ == "__main__":
    q = np.array([[1.0, 0.0], [0.0, 1.0]])
    k = np.array([[1.0, 0.0], [0.0, 1.0]])
    v = np.array([[10.0, 20.0], [30.0, 40.0]])
    att, w = scaled_dot_product_attention(q, k, v)
    print("attended:\n", att)
    print("weights:\n", w)
