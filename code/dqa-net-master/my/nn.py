"""
useful neural net modules
"""
import operator
from operator import mul
from functools import reduce

import tensorflow as tf

VERY_SMALL_NUMBER = -1e10


def softmax_with_mask(shape, x, mask, name=None):
    if name is None:
        name = softmax_with_mask.__name__
    x_masked = x + VERY_SMALL_NUMBER * (1.0 - mask)
    x_flat = tf.reshape(x_masked, [reduce(mul, shape[:-1], 1), shape[-1]])
    p_flat = tf.nn.softmax(x_flat)
    p = tf.reshape(p_flat, shape, name=name)
    return p


def softmax_with_base(shape, base_untiled, x, mask=None, name='sig'):
    if mask is not None:
        x += VERY_SMALL_NUMBER * (1.0 - mask)
    base_shape = shape[:-1] + [1]
    for _ in shape:
        base_untiled = tf.expand_dims(base_untiled, -1)
    base = tf.tile(base_untiled, base_shape)

    c_shape = shape[:-1] + [shape[-1] + 1]
    c = tf.concat(len(shape)-1, [base, x])
    c_flat = tf.reshape(c, [reduce(mul, shape[:-1], 1), c_shape[-1]])
    p_flat = tf.nn.softmax(c_flat)
    p_cat = tf.reshape(p_flat, c_shape)
    s_aug = tf.slice(p_cat, [0 for _ in shape], [i for i in shape[:-1]] + [1])
    s = tf.squeeze(s_aug, [len(shape)-1])
    sig = tf.sub(1.0, s, name="sig")
    p = tf.slice(p_cat, [0 for _ in shape[:-1]] + [1], shape)
    return sig, p


def man_sim(shape, u, v, name='man_sim'):
    """
    Manhattan similarity
    https://pdfs.semanticscholar.org/6812/fb9ef1c2dad497684a9020d8292041a639ff.pdf
    :param shape:
    :param u:
    :param v:
    :param name:
    :return:
    """
    dist = tf.reduce_sum(tf.abs(u - v), len(shape)-1)
    sim = tf.sub(0.0, dist, name=name)
    return sim


def linear(input_shape, output_dim, input_, name="linear"):
    a = input_shape[-1]
    b = output_dim
    input_flat = tf.reshape(input_, [reduce(operator.mul, input_shape[:-1], 1), a])
    with tf.variable_scope(name):
        mat = tf.get_variable("mat", shape=[a, b])
        bias = tf.get_variable("bias", shape=[b])
        out_flat = tf.matmul(input_flat, mat) + bias
        out = tf.reshape(out_flat, input_shape[:-1] + [b])
        return out


