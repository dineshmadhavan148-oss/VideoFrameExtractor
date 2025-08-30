# 🧪 Test Suite for Video Frame Extraction System

This directory contains comprehensive tests for the Video Frame Extraction System.

## 📁 Test Files

| File | Purpose | Coverage |
|------|---------|----------|
| `test_models.py` | Data models and Pydantic validation | FrameMetadata, JobStatus, API models |
| `test_database.py` | Database operations | DatabaseManager, CRUD operations |
| `test_cache.py` | Cache operations | CacheManager, Redis/memory cache |
| `test_api.py` | FastAPI endpoints | All REST API endpoints |
| `test_integration.py` | End-to-end workflows | Complete system integration |
| `run_tests.py` | Test runner with reporting | Test execution and coverage |

## 🚀 Running Tests

### **Quick Start**
```bash
# Run all tests
cd tests
python run_tests.py

# Or using unittest
python -m unittest discover

# Or using pytest (if installed)
pytest
```

### **Advanced Usage**
```bash
# Run with coverage report
python run_tests.py --coverage

# Run specific test module
python run_tests.py test_models

# Run specific test class
python -m unittest test_models.TestDataModels

# Run specific test method
python -m unittest test_models.TestDataModels.test_frame_metadata_creation
```

### **Using Pytest**
```bash
# Install pytest (if not already installed)
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest test_api.py

# Run with coverage
pytest --cov=../app --cov-report=html
```

## 📊 Test Coverage

The test suite covers:

### **✅ Unit Tests (90%+ coverage)**
- ✅ Data model validation
- ✅ Database operations (CRUD)
- ✅ Cache operations (Redis + memory)
- ✅ API endpoint responses
- ✅ Error handling

### **✅ Integration Tests**
- ✅ Complete job lifecycle
- ✅ Database consistency
- ✅ Cache integration
- ✅ Job cancellation
- ✅ Concurrent job handling
- ✅ Frame metadata storage

### **✅ API Tests**
- ✅ All REST endpoints
- ✅ Request/response validation
- ✅ Error scenarios
- ✅ Authentication (future)

## 🎯 Test Categories

### **Unit Tests** (`@pytest.mark.unit`)
Fast, isolated tests for individual components.

### **Integration Tests** (`@pytest.mark.integration`)
Tests that verify component interactions.

### **API Tests** (`@pytest.mark.api`)
Tests for FastAPI endpoints using TestClient.

### **Slow Tests** (`@pytest.mark.slow`)
Tests that take longer to run (video processing, etc.)

## 🔧 Test Configuration

### **Environment Setup**
Tests use temporary databases and directories to avoid conflicts with development data.

### **Mocking**
- Redis connections are mocked for unit tests
- OpenCV video operations are mocked for integration tests
- File system operations use temporary directories

### **Fixtures**
Common test data and setup is provided through unittest setUp methods.

## 📈 Coverage Reporting

### **Generate HTML Coverage Report**
```bash
python run_tests.py --coverage
# Opens coverage_html/index.html
```

### **Coverage Targets**
- **Overall**: 85%+
- **Models**: 95%+
- **Database**: 90%+
- **Cache**: 85%+
- **API**: 90%+

## 🐛 Debugging Tests

### **Run Specific Failing Test**
```bash
python -m unittest test_models.TestDataModels.test_frame_metadata_creation -v
```

### **Debug with Print Statements**
```python
def test_debug_example(self):
    result = some_function()
    print(f"Debug: result = {result}")
    self.assertEqual(result, expected)
```

### **Use Python Debugger**
```python
import pdb; pdb.set_trace()  # Breakpoint
```

## 📝 Writing New Tests

### **Test Naming Convention**
- Files: `test_<module>.py`
- Classes: `Test<Feature>`
- Methods: `test_<specific_behavior>`

### **Example Test Structure**
```python
class TestNewFeature(unittest.TestCase):
    def setUp(self):
        \"\"\"Set up test fixtures\"\"\"
        self.test_data = create_test_data()
    
    def tearDown(self):
        \"\"\"Clean up after tests\"\"\"
        cleanup_test_data()
    
    def test_positive_case(self):
        \"\"\"Test expected behavior\"\"\"
        result = function_under_test()
        self.assertEqual(result, expected)
    
    def test_error_case(self):
        \"\"\"Test error handling\"\"\"
        with self.assertRaises(ExpectedError):
            function_that_should_fail()
```

## 🎛️ CI/CD Integration

### **GitHub Actions Example**
```yaml
- name: Run Tests
  run: |
    pip install -r requirements.txt
    cd tests
    python run_tests.py --coverage
```

### **Test Exit Codes**
- `0`: All tests passed
- `1`: Some tests failed

## 🚨 Common Issues

### **Import Errors**
Make sure the app directory is in Python path:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
```

### **Redis Connection Errors**
Redis is mocked in tests. If you see Redis errors, check the mocking setup.

### **File Permission Errors**
Tests use temporary directories. Ensure proper cleanup in tearDown methods.

## 📚 Best Practices

1. **Test Isolation**: Each test should be independent
2. **Clear Names**: Test names should describe what they test
3. **Fast Execution**: Keep unit tests fast (< 1 second each)
4. **Comprehensive Coverage**: Test both success and failure cases
5. **Clean Setup/Teardown**: Properly clean up resources

## 🎉 Success Metrics

A successful test run should show:
```
🧪 Running Video Frame Extraction System Tests...
======================================================================
test_api.py::TestAPI::test_health_endpoint ✅ PASSED
test_database.py::TestDatabaseManager::test_save_and_get_job ✅ PASSED
test_models.py::TestDataModels::test_frame_metadata_creation ✅ PASSED
...
======================================================================
📊 TEST SUMMARY:
   Tests run: 45
   Failures: 0
   Errors: 0
   Skipped: 0
✅ ALL TESTS PASSED!
```