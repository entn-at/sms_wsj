import os
import dataclasses

import numpy as np

import lazy_dataset.database


class SmsWsj(lazy_dataset.database.JsonDatabase):
    """
    >>> from pprint import pprint
    >>> db = SmsWsj()
    >>> db.get_dataset()
    Traceback (most recent call last):
    ...
    TypeError: Missing dataset_name, use e.g.: ('cv_dev93', 'test_eval92', 'train_si284')
    >>> db.get_dataset('train_si284')
      DictDataset(len=30000)
    MapDataset(_pickle.loads)
    >>> db.get_dataset('cv_dev93')
      DictDataset(len=500)
    MapDataset(_pickle.loads)
    >>> db.get_dataset('test_eval92')
      DictDataset(len=1500)
    MapDataset(_pickle.loads)
    >>> db.get_dataset(['train_si284', 'cv_dev93', 'test_eval92'])
        DictDataset(len=30000)
      MapDataset(_pickle.loads)
        DictDataset(len=500)
      MapDataset(_pickle.loads)
        DictDataset(len=1500)
      MapDataset(_pickle.loads)
    ConcatenateDataset()
    >>> ds = db.get_dataset('cv_dev93')
    >>> pprint(ds[0], width=79-4)  # doctest: +ELLIPSIS
    {'audio_path': {'noise_image': ...,
                    'observation': ...,
                    'rir': [...,...],
                    'speech_reverberation_direct': [...,...],
                    'speech_reverberation_tail': [...,...],
                    'speech_source': [...,...]},
     'dataset': 'cv_dev93',
     'example_id': '4k0c0301_4k6c030t_0',
     'gender': ['male', 'male'],
     'kaldi_transcription': ['SAATCHI OFFICIALS SAID THE MANAGEMENT '
                             'RE:STRUCTURING MIGHT ACCELERATE ITS EFFORTS TO '
                             'PERSUADE CLIENTS TO USE THE FIRM AS A ONE STOP '
                             'SHOP FOR BUSINESS SERVICES',
                             'THEY HAVE SPENT SEVEN YEARS AND MORE THAN THREE '
                             'HUNDRED MILLION DOLLARS IN U. S. AID BUILDING '
                             "THE AREA'S BIGGEST INSURGENT FORCE"],
     'log_weights': [1.2027951449295022, -1.2027951449295022],
     'num_samples': {'observation': 103650, 'speech_source': [103650, 56335]},
     'num_speakers': 2,
     'offset': [0, 17423],
     'room_dimensions': [[8.169], [5.905], [3.073]],
     'sensor_position': [[3.899, 3.8, 3.759, 3.817, 3.916, 3.957],
                         [3.199, 3.189, 3.098, 3.017, 3.027, 3.118],
                         [1.413, 1.418, 1.423, 1.423, 1.417, 1.413]],
     'sound_decay_time': 0.354,
     'source_id': ['4k0c0301', '4k6c030t'],
     'source_position': [[2.443, 2.71], [3.104, 2.135], [1.557, 1.557]],
     'speaker_id': ['4k0', '4k6']}
    """

    @classmethod
    def default_json_path(cls):
        try:
            return os.environ['SMS_WSJ_JSON']
        except KeyError as e:
            name = cls.__name__
            raise ValueError(
                f'To instantiate the {name} database,\n'
                f'you have to provide the path to the json that\n'
                f'describes the database.\n'
                f'This can be done with\n'
                f'\t>>> `{name}(<path_to_json>)`\n'
                f'or setting the environment variable\n'
                f'\t$ export SMS_WSJ_JSON=<path_to_json>\n'
                f'and drop the argument is python\n'
                f'\t>>> `{name}()`'
            ) from e

    def __init__(self, json_path=None):
        if json_path is None:
            json_path = self.default_json_path()

        super().__init__(json_path)


@dataclasses.dataclass
class AudioReader:
    """
    Reads the audio data of an example.
    The paths are in `example['audio_path']` and will be written to
    `example['audio_data']`.
    This reader is usually used as a mapping in a dataset:

    >>> from IPython.lib.pretty import pprint
    >>> np.set_string_function(lambda a: f'array(shape={a.shape}, dtype={a.dtype})')

    >>> db = SmsWsj()
    >>> ds = db.get_dataset('cv_dev93')
    >>> ds = ds.map(AudioReader())
    >>> example = ds[0]
    >>> pprint(example['audio_data'])
    {'observation': array(shape=(6, 103650), dtype=float64),
     'speech_source': array(shape=(2, 103650), dtype=float64),
     'speech_reverberation_early': array(shape=(2, 6, 103650), dtype=float64),
     'speech_reverberation_tail': array(shape=(2, 6, 103650), dtype=float64),
     'speech_image': array(shape=(2, 6, 103650), dtype=float64),
     'noise_image': array(shape=(6, 103650), dtype=float64)}
    """

    observation: bool = True

    speech_source: bool = True
    sync_speech_source: bool = True
    # If true, pad or cut to match num samples of observation

    speech_reverberation_early: bool = True
    speech_reverberation_tail: bool = True
    speech_image: bool = True

    noise_image: bool = True

    rir: bool = False

    def __post_init__(self):
        if self.speech_image:
            self.speech_reverberation_early = True
            self.speech_reverberation_tail = True

    @classmethod
    def _rec_audio_read(cls, file):
        import soundfile

        if isinstance(file, (tuple, list)):
            return np.array([cls._rec_audio_read(f) for f in file])
        elif isinstance(file, (dict)):
            return {k: cls._rec_audio_read(v) for k, v in file.items()}
        else:
            data, sample_rate = soundfile.read(file)
            return data.T

    def __call__(self, example):
        # ToDo: np.squeeze

        data = {}
        path = example['audio_path']

        if self.observation:
            data['observation'] = self._rec_audio_read(path['observation'])
        if self.speech_source:
            data['speech_source'] = self._rec_audio_read(path['speech_source'])
            if self.sync_speech_source:
                from sms_wsj.database.utils import synchronize_speech_source
                data['speech_source'] = synchronize_speech_source(
                    data['speech_source'],
                    example['offset'],
                    T = example['num_samples']['observation'],
                )

        if self.speech_reverberation_early:
            data['speech_reverberation_early'] = self._rec_audio_read(
                path['speech_reverberation_early'])
        if self.speech_reverberation_tail:
            data['speech_reverberation_tail'] = self._rec_audio_read(
                path['speech_reverberation_tail'])

        if self.speech_image:
            data['speech_image'] = (
                data['speech_reverberation_early']
                + data['speech_reverberation_tail']
            )

        if self.noise_image:
            data['noise_image'] = self._rec_audio_read(path['noise_image'])

        if self.rir:
            data['rir'] = self._rec_audio_read(path['rir'])

        example['audio_data'] = data

        return example
