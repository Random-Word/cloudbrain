import json
import logging
import csv
import time
import os

from cloudbrain.modules.interface import ModuleInterface

_LOGGER = logging.getLogger(__name__)


def _clean_key(key):
    """
    Strip the colons from routing key names and return a
    name more appropriate for writing output files.
    This should probably be moved to a cloudbrain library if it
    ends up being a standard method of generating output files.
    key: A routing key string
    return: The key with colons replaced with underscores
    """
    return '_'.join(key.split(':')) if ':' in key else key


class CSVOutSink(ModuleInterface):
    def __init__(self, subscribers, publishers, out_dir):
        """
        Set up the CSV writers for each subscribed topic and metric
        TODO: Delete, back up, or warn of existing files to prevent
        new headers from corrupting existing data.
        """
        thread_event=False
        super(CSVOutSink, self).__init__(subscribers, publishers)
        _LOGGER.debug("Subscribers: %s" % self.subscribers)
        _LOGGER.debug("Publishers: %s" % self.publishers)

        if not os.path.exists(out_dir):
            _LOGGER.info("Creating missing directory {}".format(out_dir))
            os.mkdir(out_dir)

        self.thread_event = thread_event
        self.headers = {}
        self.file_name_pattern = '{base_routing_key}_{metric_name}.csv'
        self.out_files = {}
        # For each subscriber, get each routing key
        for subscriber in self.subscribers:
            base_routing_key = subscriber.base_routing_key
            # For each metric buffer in the router open a file handle
            # and save the corresponding CSV writer object
            for metric_buffer in subscriber.metric_buffers.values():
                num_channels = metric_buffer.num_channels
                d = {'base_routing_key': _clean_key(base_routing_key),
                     'metric_name': metric_buffer.name}
                file_name = self.file_name_pattern.format(**d)
                _LOGGER.info("Opening file: {}".format(file_name))
                f = open(os.path.join(out_dir, file_name), 'w+')
                writer = csv.writer(f)
                headers = metric_buffer.metric_names
                self.headers[file_name] = headers
                writer.writerow(headers)
                self.out_files[file_name] = writer

    def _csv_callback_factory(self, file_name):
        def _csv_callback(unsed_ch, unsed_method, unsed_properties, json_string):
            """
            Parse a JSON data message and write its contents to the appropriate
            CSV
            """
            writer = self.out_files[file_name]
            data_buffer = json.loads(json_string)
            for data in data_buffer:
                writer.writerow([data[h] for h in self.headers[file_name]])

        return _csv_callback

    def start(self):
        """
        Iterate through subscribers and metrics to build
        callback functions for each.
        """
        for subscriber in self.subscribers:
            base_routing_key = subscriber.base_routing_key
            for metric_buffer in subscriber.metric_buffers.values():
                num_channels = metric_buffer.num_channels
                d = {'base_routing_key': _clean_key(base_routing_key),
                     'metric_name': metric_buffer.name}
                file_name = self.file_name_pattern.format(**d)
                csv_callback = self._csv_callback_factory(file_name)
                routing_key = subscriber.base_routing_key
                _LOGGER.debug('Subscribing to %s' % metric_buffer.name)
                subscriber.subscribe(metric_buffer.name, csv_callback)
        while self.thread_event:
            time.sleep(1)


