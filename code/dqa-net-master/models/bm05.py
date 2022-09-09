import itertools
import json
import os

import numpy as np
import tensorflow as tf

from my.tensorflow import average_gradients
from read_data.r05 import DataSet
from utils import get_pbar


class BaseRunner(object):
    def __init__(self, params, sess, towers):
        assert isinstance(sess, tf.Session)
        self.sess = sess
        self.params = params
        self.towers = towers
        self.num_towers = len(towers)
        self.placeholders = {}
        self.tensors = {}
        self.saver = None
        self.writer = None
        self.initialized = False

    def initialize(self):
        params = self.params
        sess = self.sess
        device_type = params.device_type
        summaries = []

        global_step = tf.get_variable('global_step', shape=[], dtype='int32',
                                      initializer=tf.constant_initializer(0), trainable=False)
        self.tensors['global_step'] = global_step

        epoch = tf.get_variable('epoch', shape=[], dtype='int32',
                                initializer=tf.constant_initializer(0), trainable=False)
        self.tensors['epoch'] = epoch

        learning_rate = tf.placeholder('float32', name='learning_rate')
        summaries.append(tf.scalar_summary("learning_rate", learning_rate))
        self.placeholders['learning_rate'] = learning_rate

        if params.opt == 'basic':
            opt = tf.train.GradientDescentOptimizer(learning_rate)
        elif params.opt == 'adagrad':
            opt = tf.train.AdagradOptimizer(learning_rate)
        else:
            raise Exception()

        grads_tensors = []
        correct_tensors = []
        loss_tensors = []
        for device_id, tower in enumerate(self.towers):
            with tf.device("/%s:%d" % (device_type, device_id)), tf.name_scope("%s_%d" % (device_type, device_id)) as scope:
                tower.initialize(scope)
                tf.get_variable_scope().reuse_variables()
                loss_tensor = tower.get_loss_tensor()
                loss_tensors.append(loss_tensor)
                correct_tensor = tower.get_correct_tensor()
                correct_tensors.append(correct_tensor)
                grads_tensor = opt.compute_gradients(loss_tensor)
                grads_tensors.append(grads_tensor)

        with tf.name_scope("gpu_sync"):
            loss_tensor = tf.reduce_mean(tf.pack(loss_tensors), 0, name='loss')
            correct_tensor = tf.concat(0, correct_tensors, name="correct")
            with tf.name_scope("average_gradients"):
                grads_tensor = average_gradients(grads_tensors)

        self.tensors['loss'] = loss_tensor
        self.tensors['correct'] = correct_tensor
        summaries.append(tf.scalar_summary(loss_tensor.op.name, loss_tensor))

        for grad, var in grads_tensor:
            if grad is not None:
                summaries.append(tf.histogram_summary(var.op.name+'/gradients', grad))
        self.tensors['grads'] = grads_tensor

        for var in tf.trainable_variables():
            summaries.append(tf.histogram_summary(var.op.name, var))

        apply_grads_op = opt.apply_gradients(grads_tensor, global_step=global_step)

        train_op = tf.group(apply_grads_op)
        self.tensors['train'] = train_op

        saver = tf.train.Saver(tf.all_variables())
        self.saver = saver

        summary_op = tf.merge_summary(summaries)
        self.tensors['summary'] = summary_op

        init_op = tf.initialize_all_variables()
        sess.run(init_op)
        self.writer = tf.train.SummaryWriter(params.log_dir, sess.graph)
        self.initialized = True

    def _get_feed_dict(self, batches, mode, **kwargs):
        placeholders = self.placeholders
        learning_rate_ph = placeholders['learning_rate']
        learning_rate = kwargs['learning_rate'] if mode == 'train' else 0.0
        feed_dict = {learning_rate_ph: learning_rate}
        for tower_idx, tower in enumerate(self.towers):
            batch = batches[tower_idx] if tower_idx < len(batches) else None
            cur_feed_dict = tower.get_feed_dict(batch, mode, **kwargs)
            feed_dict.update(cur_feed_dict)
        return feed_dict

    def _train_batches(self, batches, **kwargs):
        sess = self.sess
        tensors = self.tensors
        feed_dict = self._get_feed_dict(batches, 'train', **kwargs)
        ops = [tensors[name] for name in ['train', 'summary', 'global_step']]
        train, summary, global_step = sess.run(ops, feed_dict=feed_dict)
        return train, summary, global_step

    def _eval_batches(self, batches, eval_tensor_names=()):
        sess = self.sess
        tensors = self.tensors
        num_examples = sum(len(batch[0]) for batch in batches)
        feed_dict = self._get_feed_dict(batches, 'eval')
        ops = [tensors[name] for name in ['correct', 'loss', 'summary', 'global_step']]
        correct, loss, summary, global_step = sess.run(ops, feed_dict=feed_dict)
        num_corrects = np.sum(correct[:num_examples])
        if len(eval_tensor_names) > 0:
            valuess = [sess.run([tower.tensors[name] for name in eval_tensor_names], feed_dict=feed_dict)
                       for tower in self.towers]
        else:
            valuess = [[]]

        return (num_corrects, loss, summary, global_step), valuess

    def train(self, train_data_set, val_data_set=None, eval_tensor_names=()):
        assert isinstance(train_data_set, DataSet)
        assert self.initialized, "Initialize tower before training."
        # TODO : allow partial batch

        sess = self.sess
        writer = self.writer
        params = self.params
        num_epochs = params.num_epochs
        num_batches = params.train_num_batches if params.train_num_batches >= 0 else train_data_set.get_num_batches(partial=False)
        num_iters_per_epoch = int(num_batches / self.num_towers)
        num_digits = int(np.log10(num_batches))

        epoch_op = self.tensors['epoch']
        epoch = sess.run(epoch_op)
        print("training %d epochs ... " % num_epochs)
        print("num iters per epoch: %d" % num_iters_per_epoch)
        print("starting from epoch %d." % (epoch+1))
        while epoch < num_epochs:
            train_args = self._get_train_args(epoch)
            pbar = get_pbar(num_iters_per_epoch, "epoch %s|" % str(epoch+1).zfill(num_digits)).start()
            for iter_idx in range(num_iters_per_epoch):
                batches = [train_data_set.get_next_labeled_batch() for _ in range(self.num_towers)]
                _, summary, global_step = self._train_batches(batches, **train_args)
                writer.add_summary(summary, global_step)
                pbar.update(iter_idx)
            pbar.finish()
            train_data_set.complete_epoch()

            assign_op = epoch_op.assign_add(1)
            _, epoch = sess.run([assign_op, epoch_op])

            if val_data_set and epoch % params.val_period == 0:
                self.eval(train_data_set, is_val=True, eval_tensor_names=eval_tensor_names)
                self.eval(val_data_set, is_val=True, eval_tensor_names=eval_tensor_names)

            if epoch % params.save_period == 0:
                self.save()

    def eval(self, data_set, is_val=False, eval_tensor_names=()):
        assert isinstance(data_set, DataSet)
        assert self.initialized, "Initialize tower before training."

        params = self.params
        sess = self.sess
        epoch_op = self.tensors['epoch']
        dn = data_set.get_num_batches(partial=True)
        if is_val:
            pn = params.val_num_batches
            num_batches = pn if 0 <= pn <= dn else dn
        else:
            pn = params.test_num_batches
            num_batches = pn if 0 <= pn <= dn else dn
        num_iters = int(np.ceil(num_batches / self.num_towers))
        num_corrects, total = 0, 0
        eval_values = []
        idxs = []
        losses = []
        N = data_set.batch_size * num_batches
        if N > data_set.num_examples:
            N = data_set.num_examples
        string = "eval on %s, N=%d|" % (data_set.name, N)
        pbar = get_pbar(num_iters, prefix=string).start()
        for iter_idx in range(num_iters):
            batches = []
            for _ in range(self.num_towers):
                if data_set.has_next_batch(partial=True):
                    idxs.extend(data_set.get_batch_idxs(partial=True))
                    batches.append(data_set.get_next_labeled_batch(partial=True))
            (cur_num_corrects, cur_loss, _, global_step), eval_value_batches = \
                self._eval_batches(batches, eval_tensor_names=eval_tensor_names)
            num_corrects += cur_num_corrects
            total += sum(len(batch[0]) for batch in batches)
            for eval_value_batch in eval_value_batches:
                eval_values.append([x.tolist() for x in eval_value_batch])  # numpy.array.toList
            losses.append(cur_loss)
            pbar.update(iter_idx)
        pbar.finish()
        loss = np.mean(losses)
        data_set.reset()

        epoch = sess.run(epoch_op)
        print("at epoch %d: acc = %.2f%% = %d / %d, loss = %.4f" %
              (epoch, 100 * float(num_corrects)/total, num_corrects, total, loss))

        # For outputting eval json files
        ids = [data_set.idx2id[idx] for idx in idxs]
        zipped_eval_values = [list(itertools.chain(*each)) for each in zip(*eval_values)]
        values = {name: values for name, values in zip(eval_tensor_names, zipped_eval_values)}
        out = {'ids': ids, 'values': values}
        eval_path = os.path.join(params.eval_dir, "%s_%s.json" % (data_set.name, str(epoch).zfill(4)))
        json.dump(out, open(eval_path, 'w'))

    def _get_train_args(self, epoch_idx):
        params = self.params
        learning_rate = params.init_lr

        anneal_period = params.lr_anneal_period
        anneal_ratio = params.lr_anneal_ratio
        num_periods = int(epoch_idx / anneal_period)
        factor = anneal_ratio ** num_periods
        learning_rate *= factor

        train_args = {'learning_rate': learning_rate}
        return train_args

    def save(self):
        assert self.initialized, "Initialize tower before saving."

        sess = self.sess
        params = self.params
        save_dir = params.save_dir
        name = params.model_name
        global_step = self.tensors['global_step']
        print("saving model ...")
        save_path = os.path.join(save_dir, name)
        self.saver.save(sess, save_path, global_step)
        print("saving done.")

    def load(self):
        assert self.initialized, "Initialize tower before loading."

        sess = self.sess
        params = self.params
        save_dir = params.save_dir
        print("loading model ...")
        checkpoint = tf.train.get_checkpoint_state(save_dir)
        assert checkpoint is not None, "Cannot load checkpoint at %s" % save_dir
        self.saver.restore(sess, checkpoint.model_checkpoint_path)
        print("loading done.")


class BaseTower(object):
    def __init__(self, params):
        self.params = params
        self.placeholders = {}
        self.tensors = {}
        self.default_initializer = tf.random_normal_initializer(params.init_mean, params.init_std)

    def initialize(self, scope):
        # Actual building
        # Separated so that GPU assignment can be done here.
        raise Exception("Implement this!")

    def get_correct_tensor(self):
        return self.tensors['correct']

    def get_loss_tensor(self):
        return self.tensors['loss']

    def get_feed_dict(self, batch, mode, **kwargs):
        raise Exception("Implment this!")
