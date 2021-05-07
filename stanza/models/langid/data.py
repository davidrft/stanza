import json
import random
import torch


class DataLoader:
    """
    Class for loading language id data and providing batches
    """

    def __init__(self, use_gpu=None):
        self.batches = None
        self.batches_iter = None
        self.lang_weights = None
        # set self.use_gpu and self.device
        if use_gpu is None:
            self.use_gpu = torch.cuda.is_available()
        else:
            self.use_gpu = use_gpu
        if self.use_gpu:
            self.device = torch.device("cuda")
        else:
            self.device = None

    def load_data(self, batch_size, data_files, char_index, tag_index, randomize=False):
        """
        Load sequence data and labels, calculate weights for weighted cross entropy loss.
        Data is stored in a file, 1 example per line
        Example: {"text": "Hello world.", "label": "en"}
        """

        # set up lang counts used for weights for cross entropy loss
        lang_counts = [0 for _ in tag_index]

        # set up examples from data files
        examples = []
        for data_file in data_files:
            examples += [x for x in open(data_file).read().split("\n") if x.strip()]
        random.shuffle(examples)
        examples = [json.loads(x) for x in examples]

        # randomize data
        if randomize:
            split_examples = []
            for example in examples:
                sequence = example["text"]
                label = example["label"]
                sequences = DataLoader.randomize_data([sequence])
                split_examples += [{"text": seq, "label": label} for seq in sequences]
            examples = split_examples
            random.shuffle(examples)

        # break into equal length batches
        batch_lengths = {}
        for example in examples:
            sequence = example["text"]
            label = example["label"]
            if len(sequence) not in batch_lengths:
                batch_lengths[len(sequence)] = []
            sequence_as_list = [char_index.get(c, char_index["UNK"]) for c in list(sequence)]
            batch_lengths[len(sequence)].append((sequence_as_list, tag_index[label]))
            lang_counts[tag_index[label]] += 1
        for length in batch_lengths:
            random.shuffle(batch_lengths[length])

        # create final set of batches
        batches = []
        for length in batch_lengths:
            for sublist in [batch_lengths[length][i:i + batch_size] for i in
                            range(0, len(batch_lengths[length]), batch_size)]:
                batches.append(sublist)

        self.batches = [self.build_batch_tensors(batch) for batch in batches]

        # set up lang weights
        most_frequent = max(lang_counts)
        for idx in range(len(lang_counts)):
            lang_counts[idx] = float(most_frequent) / float(lang_counts[idx])

        self.lang_weights = torch.tensor(lang_counts, device=self.device, dtype=torch.float)

        # shuffle batches to mix up lengths
        random.shuffle(self.batches)
        self.batches_iter = iter(self.batches)

    @staticmethod
    def randomize_data(sentences, upper_lim=20, lower_lim=5):
        """
        Takes the original data and creates random length examples with length between upper limit and lower limit
        From LSTM_langid: https://github.com/AU-DIS/LSTM_langid/blob/main/src/language_datasets.py
        """

        new_data = []
        for sentence in sentences:
            remaining = sentence
            while lower_lim < len(remaining):
                lim = random.randint(lower_lim, upper_lim)
                m = min(len(remaining), lim)
                new_sentence = remaining[:m]
                new_data.append(new_sentence)
                split = remaining[m:].split(" ", 1)
                if len(split) <= 1:
                    break
                remaining = split[1]
        random.shuffle(new_data)
        return new_data

    def build_batch_tensors(self, batch):
        """
        Helper to turn batches into tensors
        """

        batch_tensors = dict()
        batch_tensors["sentences"] = torch.tensor([s[0] for s in batch], device=self.device, dtype=torch.long)
        batch_tensors["targets"] = torch.tensor([s[1] for s in batch], device=self.device, dtype=torch.long)

        return batch_tensors

    def next(self):
        return next(self.batches_iter)