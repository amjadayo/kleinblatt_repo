# Test Suite for Production Tracker

This test suite verifies the core functionality of the Production Tracker application, with a focus on the database operations that form the heart of the app.

## Test Organization

The test suite is organized into the following files:

- `conftest.py`: Contains pytest fixtures for database setup and sample data
- `test_database.py`: Tests core database operations (calculate_production_date, generate_subscription_orders)
- `test_edit_scope.py`: Tests the subscription update scope functionality (updating current order vs. future orders)
- `test_view_integration.py`: Tests that changes to orders are correctly reflected in the schedules
- `test_system_integration.py`: End-to-end system tests covering the complete workflow
- `run_manual_test.py`: Script for manual testing of database operations

## Running the Tests

To run the tests, you'll need to install pytest and any other dependencies:

```bash
pip install -r tests/requirements.txt
```

Then, from the project root directory, run:

```bash
python -m pytest tests/
```

To run a specific test file:

```bash
python -m pytest tests/test_edit_scope.py
```

To run a specific test:

```bash
python -m pytest tests/test_edit_scope.py::test_update_single_order_scope
```

To see more detailed output, use the `-v` flag:

```bash
python -m pytest -v tests/
```

To generate a coverage report:

```bash
python -m pytest --cov=. tests/
```

## Manual Testing

For manual testing, you can run:

```bash
python tests/run_manual_test.py
```

This script will:
1. Create test customers, items, and orders
2. Test editing a single order
3. Test editing a subscription
4. Test the delivery schedule, production plan, and transfer schedule
5. Test deleting an order
6. Clean up all test data

## Test Coverage

These tests focus on the core database functionality that powers the application:

1. **Order Management**
   - Creating orders with and without subscriptions
   - Editing orders (single order or future orders)
   - Deleting orders (single order or future orders)

2. **Subscription Management**
   - Generating subscription orders
   - Updating subscription parameters
   - Adding new orders to existing subscriptions

3. **Schedule Integration**
   - Verifying changes to orders are reflected in delivery schedule
   - Verifying changes to orders are reflected in production plan
   - Verifying changes to orders are reflected in transfer schedule

## In-Memory Database

The tests use an in-memory SQLite database to ensure tests are fast and do not affect the production database. This approach also guarantees that each test starts with a clean database state.

## Troubleshooting

### Common Issues

1. **Database connection errors**: 
   - Ensure the database is properly initialized and closed in each test
   - The `test_db` fixture in `conftest.py` should handle this automatically

2. **Date format issues**:
   - Use the `normalize_date` helper function from `conftest.py` for comparing dates
   - Different parts of the app may use different date formats (YYYY-MM-DD vs DD.MM.YYYY)

3. **Missing items in schedules**:
   - Ensure dates used in schedules match the exact format expected
   - Double-check production_date calculations based on item growth periods

### Debugging Tips

1. For more verbose output, run tests with the `-v` flag and `--capture=no` to see print statements:
   ```bash
   python -m pytest -v --capture=no tests/test_file.py
   ```

2. To debug database issues, add print statements in your tests:
   ```python
   print("Checking order:", order.id, "with delivery date:", order.delivery_date)
   ```

3. For complex failures, use pytest's `-x` flag to stop at the first failure:
   ```bash
   python -m pytest -xvs tests/
   ```

4. If tests are failing because of database connection issues, check for proper cleanup:
   ```python
   print("DB connection state:", db.is_closed())
   ```

## Adding New Tests

When adding new tests:

1. Follow the naming convention `test_*.py` for files and `test_*` for function names
2. Use the `test_db` fixture to ensure proper database setup and cleanup
3. Use the `sample_data` fixture for common test data
4. Add meaningful assertions to verify the expected behavior
5. Clean up any test data created specifically for that test 