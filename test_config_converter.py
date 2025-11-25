import unittest
import tempfile
import os
from config_converter import ConfigParser

class TestConfigConverter(unittest.TestCase):
    def setUp(self):
        self.parser = ConfigParser()
    
    def test_numbers(self):
        text = "port = 8080;"
        result = self.parser.parse(text)
        self.assertEqual(result, {'port': 8080})
        
        text = "temperature = -25.5;"
        result = self.parser.parse(text)
        self.assertEqual(result, {'temperature': -25.5})
    
    def test_arrays(self):
        text = "colors = array(red, green, blue);"
        result = self.parser.parse(text)
        self.assertEqual(result, {'colors': ['red', 'green', 'blue']})
        
        text = "matrix = array(array(1, 2), array(3, 4));"
        result = self.parser.parse(text)
        self.assertEqual(result, {'matrix': [[1, 2], [3, 4]]})
    
    def test_constants(self):
        text = """
        (def max_connections 100);
        connections = {max_connections};
        """
        result = self.parser.parse(text)
        self.assertEqual(result, {'connections': 100})
    
    def test_complex_expressions(self):
        text = """
        (def base_port 8000);
        (def services array(api, db, cache));
        
        port = {base_port};
        active_services = {services};
        timeout = 30;
        """
        result = self.parser.parse(text)
        expected = {
            'port': 8000,
            'active_services': ['api', 'db', 'cache'],
            'timeout': 30
        }
        self.assertEqual(result, expected)
    
    def test_comments(self):
        text = """
        C Это однострочный комментарий
        name = value; C комментарий после кода
        --[[
        Это многострочный
        комментарий
        ]]
        number = 42;
        """
        result = self.parser.parse(text)
        self.assertEqual(result, {'name': 'value', 'number': 42})
    
    def test_syntax_errors(self):
        with self.assertRaises(SyntaxError):
            text = "unknown_var = unknown_value;"
            self.parser.parse(text)
        
        with self.assertRaises(SyntaxError):
            text = "var = {unknown_constant};"
            self.parser.parse(text)
    
    def test_nested_arrays_with_constants(self):
        text = """
        (def sizes array(10, 20, 30));
        (def default_size 15);
        
        config = array(
            {sizes},
            array({default_size}, 25),
            {default_size}
        );
        """
        result = self.parser.parse(text)
        expected = {
            'config': [
                [10, 20, 30],
                [15, 25],
                15
            ]
        }
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
