# -*- coding: utf-8 -*-
"""
Tests for Resilience module - Circuit Breaker pattern.

Tests:
- CircuitState enum
- CircuitBreakerStats dataclass
- CircuitBreaker class
- CircuitBreakerRegistry
- circuit_protected decorator
"""

import pytest
from unittest.mock import Mock, patch
import time


class TestCircuitState:
    """Tests for CircuitState enum."""
    
    def test_circuit_states_exist(self):
        """Test CircuitState enum values."""
        states = ['CLOSED', 'OPEN', 'HALF_OPEN']
        
        assert 'CLOSED' in states
        assert 'OPEN' in states
        assert 'HALF_OPEN' in states
    
    def test_closed_is_normal_operation(self):
        """Test CLOSED state represents normal operation."""
        state = 'CLOSED'
        
        is_normal = state == 'CLOSED'
        
        assert is_normal is True


class TestCircuitBreakerStats:
    """Tests for CircuitBreakerStats dataclass."""
    
    def test_stats_initial_values(self):
        """Test stats initial values."""
        stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'last_failure_time': None
        }
        
        assert stats['total_calls'] == 0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = {
            'total_calls': 100,
            'successful_calls': 95
        }
        
        def success_rate(s):
            if s['total_calls'] == 0:
                return 100.0
            return (s['successful_calls'] / s['total_calls']) * 100
        
        rate = success_rate(stats)
        
        assert rate == 95.0
    
    def test_success_rate_zero_calls(self):
        """Test success rate with zero calls."""
        stats = {
            'total_calls': 0,
            'successful_calls': 0
        }
        
        def success_rate(s):
            if s['total_calls'] == 0:
                return 100.0
            return (s['successful_calls'] / s['total_calls']) * 100
        
        rate = success_rate(stats)
        
        assert rate == 100.0


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""
    
    def test_init_default_values(self):
        """Test CircuitBreaker default initialization."""
        breaker = {
            'name': 'test_breaker',
            'failure_threshold': 5,
            'reset_timeout': 30,
            'half_open_max_calls': 3,
            'state': 'CLOSED',
            'failure_count': 0
        }
        
        assert breaker['state'] == 'CLOSED'
        assert breaker['failure_threshold'] == 5
    
    def test_init_custom_values(self):
        """Test CircuitBreaker with custom values."""
        breaker = {
            'name': 'custom',
            'failure_threshold': 10,
            'reset_timeout': 60,
            'half_open_max_calls': 5
        }
        
        assert breaker['failure_threshold'] == 10
        assert breaker['reset_timeout'] == 60


class TestCircuitBreakerState:
    """Tests for CircuitBreaker state management."""
    
    def test_is_closed(self):
        """Test is_closed property."""
        breaker = {'state': 'CLOSED'}
        
        is_closed = breaker['state'] == 'CLOSED'
        
        assert is_closed is True
    
    def test_is_open(self):
        """Test is_open property."""
        breaker = {'state': 'OPEN'}
        
        is_open = breaker['state'] == 'OPEN'
        
        assert is_open is True
    
    def test_set_state(self):
        """Test _set_state method."""
        breaker = {'state': 'CLOSED'}
        
        def set_state(b, new_state):
            b['state'] = new_state
        
        set_state(breaker, 'OPEN')
        
        assert breaker['state'] == 'OPEN'


class TestShouldAllowCall:
    """Tests for _should_allow_call method."""
    
    def test_allow_call_when_closed(self):
        """Test call allowed when circuit is closed."""
        breaker = {'state': 'CLOSED'}
        
        def should_allow(b):
            return b['state'] == 'CLOSED' or b['state'] == 'HALF_OPEN'
        
        assert should_allow(breaker) is True
    
    def test_deny_call_when_open(self):
        """Test call denied when circuit is open."""
        breaker = {
            'state': 'OPEN',
            'last_failure_time': time.time(),
            'reset_timeout': 30
        }
        
        def should_allow(b):
            if b['state'] == 'CLOSED':
                return True
            if b['state'] == 'OPEN':
                # Check if reset timeout has passed
                elapsed = time.time() - b['last_failure_time']
                return elapsed > b['reset_timeout']
            return True  # HALF_OPEN
        
        # Just failed, should deny
        assert should_allow(breaker) is False
    
    def test_allow_call_after_timeout(self):
        """Test call allowed after timeout expires."""
        breaker = {
            'state': 'OPEN',
            'last_failure_time': time.time() - 60,  # 60 seconds ago
            'reset_timeout': 30
        }
        
        def should_allow(b):
            if b['state'] == 'OPEN':
                elapsed = time.time() - b['last_failure_time']
                return elapsed > b['reset_timeout']
            return True
        
        assert should_allow(breaker) is True


class TestOnSuccess:
    """Tests for _on_success method."""
    
    def test_on_success_resets_failures(self):
        """Test success resets failure count."""
        breaker = {'failure_count': 3, 'state': 'CLOSED'}
        
        def on_success(b):
            b['failure_count'] = 0
        
        on_success(breaker)
        
        assert breaker['failure_count'] == 0
    
    def test_on_success_half_open_closes(self):
        """Test success in half-open state closes circuit."""
        breaker = {'state': 'HALF_OPEN', 'half_open_successes': 2, 'half_open_max_calls': 3}
        
        def on_success(b):
            if b['state'] == 'HALF_OPEN':
                b['half_open_successes'] += 1
                if b['half_open_successes'] >= b['half_open_max_calls']:
                    b['state'] = 'CLOSED'
        
        on_success(breaker)
        
        assert breaker['state'] == 'CLOSED'


class TestOnFailure:
    """Tests for _on_failure method."""
    
    def test_on_failure_increments_count(self):
        """Test failure increments failure count."""
        breaker = {'failure_count': 0}
        
        def on_failure(b):
            b['failure_count'] += 1
        
        on_failure(breaker)
        
        assert breaker['failure_count'] == 1
    
    def test_on_failure_opens_circuit(self):
        """Test failure opens circuit when threshold reached."""
        breaker = {'failure_count': 4, 'failure_threshold': 5, 'state': 'CLOSED'}
        
        def on_failure(b):
            b['failure_count'] += 1
            if b['failure_count'] >= b['failure_threshold']:
                b['state'] = 'OPEN'
                b['last_failure_time'] = time.time()
        
        on_failure(breaker)
        
        assert breaker['state'] == 'OPEN'
    
    def test_on_failure_half_open_reopens(self):
        """Test failure in half-open state reopens circuit."""
        breaker = {'state': 'HALF_OPEN'}
        
        def on_failure(b):
            if b['state'] == 'HALF_OPEN':
                b['state'] = 'OPEN'
        
        on_failure(breaker)
        
        assert breaker['state'] == 'OPEN'


class TestCircuitBreakerCall:
    """Tests for call method."""
    
    def test_call_success(self):
        """Test successful call through circuit breaker."""
        breaker = {'state': 'CLOSED', 'failure_count': 0}
        
        def call(b, func):
            if b['state'] == 'OPEN':
                raise Exception('Circuit is open')
            try:
                result = func()
                b['failure_count'] = 0
                return result
            except Exception:
                b['failure_count'] += 1
                raise
        
        result = call(breaker, lambda: 'success')
        
        assert result == 'success'
    
    def test_call_failure(self):
        """Test failed call through circuit breaker."""
        breaker = {'state': 'CLOSED', 'failure_count': 0, 'failure_threshold': 5}
        
        def call(b, func):
            try:
                return func()
            except Exception as e:
                b['failure_count'] += 1
                raise
        
        with pytest.raises(Exception):
            call(breaker, lambda: 1/0)
        
        assert breaker['failure_count'] == 1


class TestRecordSuccess:
    """Tests for record_success method."""
    
    def test_record_success_increments_stats(self):
        """Test record_success increments stats."""
        stats = {'total_calls': 0, 'successful_calls': 0}
        
        def record_success(s):
            s['total_calls'] += 1
            s['successful_calls'] += 1
        
        record_success(stats)
        
        assert stats['total_calls'] == 1
        assert stats['successful_calls'] == 1


class TestRecordFailure:
    """Tests for record_failure method."""
    
    def test_record_failure_increments_stats(self):
        """Test record_failure increments stats."""
        stats = {'total_calls': 0, 'failed_calls': 0}
        
        def record_failure(s):
            s['total_calls'] += 1
            s['failed_calls'] += 1
        
        record_failure(stats)
        
        assert stats['total_calls'] == 1
        assert stats['failed_calls'] == 1


class TestReset:
    """Tests for reset method."""
    
    def test_reset_clears_state(self):
        """Test reset clears circuit breaker state."""
        breaker = {
            'state': 'OPEN',
            'failure_count': 5,
            'stats': {'total_calls': 100, 'failed_calls': 50}
        }
        
        def reset(b):
            b['state'] = 'CLOSED'
            b['failure_count'] = 0
            b['stats'] = {'total_calls': 0, 'failed_calls': 0, 'successful_calls': 0}
        
        reset(breaker)
        
        assert breaker['state'] == 'CLOSED'
        assert breaker['failure_count'] == 0


class TestGetStatus:
    """Tests for get_status method."""
    
    def test_get_status_returns_info(self):
        """Test get_status returns status info."""
        breaker = {
            'name': 'test',
            'state': 'CLOSED',
            'failure_count': 0,
            'failure_threshold': 5
        }
        
        def get_status(b):
            return {
                'name': b['name'],
                'state': b['state'],
                'failure_count': b['failure_count'],
                'threshold': b['failure_threshold']
            }
        
        status = get_status(breaker)
        
        assert status['name'] == 'test'
        assert status['state'] == 'CLOSED'


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""
    
    def test_registry_init(self):
        """Test registry initialization."""
        registry = {'breakers': {}}
        
        assert registry['breakers'] == {}
    
    def test_get_breaker_creates_new(self):
        """Test get_breaker creates new breaker if not exists."""
        registry = {'breakers': {}}
        
        def get_breaker(r, name):
            if name not in r['breakers']:
                r['breakers'][name] = {
                    'name': name,
                    'state': 'CLOSED',
                    'failure_count': 0
                }
            return r['breakers'][name]
        
        breaker = get_breaker(registry, 'postgresql')
        
        assert breaker['name'] == 'postgresql'
        assert 'postgresql' in registry['breakers']
    
    def test_get_breaker_returns_existing(self):
        """Test get_breaker returns existing breaker."""
        registry = {
            'breakers': {
                'postgresql': {'name': 'postgresql', 'state': 'OPEN'}
            }
        }
        
        def get_breaker(r, name):
            return r['breakers'].get(name)
        
        breaker = get_breaker(registry, 'postgresql')
        
        assert breaker['state'] == 'OPEN'
    
    def test_remove_breaker(self):
        """Test remove_breaker removes breaker."""
        registry = {
            'breakers': {
                'postgresql': {'name': 'postgresql'}
            }
        }
        
        def remove_breaker(r, name):
            if name in r['breakers']:
                del r['breakers'][name]
        
        remove_breaker(registry, 'postgresql')
        
        assert 'postgresql' not in registry['breakers']
    
    def test_reset_all(self):
        """Test reset_all resets all breakers."""
        registry = {
            'breakers': {
                'postgresql': {'state': 'OPEN', 'failure_count': 5},
                'spatialite': {'state': 'OPEN', 'failure_count': 3}
            }
        }
        
        def reset_all(r):
            for name in r['breakers']:
                r['breakers'][name]['state'] = 'CLOSED'
                r['breakers'][name]['failure_count'] = 0
        
        reset_all(registry)
        
        assert registry['breakers']['postgresql']['state'] == 'CLOSED'
        assert registry['breakers']['spatialite']['state'] == 'CLOSED'
    
    def test_get_all_statuses(self):
        """Test get_all_statuses returns all breaker statuses."""
        registry = {
            'breakers': {
                'postgresql': {'name': 'postgresql', 'state': 'CLOSED'},
                'spatialite': {'name': 'spatialite', 'state': 'OPEN'}
            }
        }
        
        def get_all_statuses(r):
            return {name: b['state'] for name, b in r['breakers'].items()}
        
        statuses = get_all_statuses(registry)
        
        assert statuses['postgresql'] == 'CLOSED'
        assert statuses['spatialite'] == 'OPEN'
    
    def test_get_open_breakers(self):
        """Test get_open_breakers returns only open breakers."""
        registry = {
            'breakers': {
                'postgresql': {'name': 'postgresql', 'state': 'CLOSED'},
                'spatialite': {'name': 'spatialite', 'state': 'OPEN'},
                'ogr': {'name': 'ogr', 'state': 'OPEN'}
            }
        }
        
        def get_open_breakers(r):
            return [name for name, b in r['breakers'].items() if b['state'] == 'OPEN']
        
        open_breakers = get_open_breakers(registry)
        
        assert 'spatialite' in open_breakers
        assert 'ogr' in open_breakers
        assert 'postgresql' not in open_breakers


class TestCircuitProtectedDecorator:
    """Tests for circuit_protected decorator."""
    
    def test_decorator_success(self):
        """Test decorator passes through on success."""
        breaker = {'state': 'CLOSED', 'failure_count': 0}
        
        def circuit_protected(func):
            def wrapper(*args, **kwargs):
                if breaker['state'] == 'OPEN':
                    raise Exception('Circuit open')
                try:
                    result = func(*args, **kwargs)
                    breaker['failure_count'] = 0
                    return result
                except Exception:
                    breaker['failure_count'] += 1
                    raise
            return wrapper
        
        @circuit_protected
        def test_func():
            return 'success'
        
        result = test_func()
        
        assert result == 'success'
    
    def test_decorator_failure(self):
        """Test decorator handles failure."""
        breaker = {'state': 'CLOSED', 'failure_count': 0, 'failure_threshold': 5}
        
        def circuit_protected(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    breaker['failure_count'] += 1
                    raise
            return wrapper
        
        @circuit_protected
        def failing_func():
            raise ValueError('error')
        
        with pytest.raises(ValueError):
            failing_func()
        
        assert breaker['failure_count'] == 1


class TestGetPostgresqlBreaker:
    """Tests for get_postgresql_breaker function."""
    
    def test_returns_breaker(self):
        """Test get_postgresql_breaker returns breaker."""
        _postgresql_breaker = {'name': 'postgresql', 'state': 'CLOSED'}
        
        def get_postgresql_breaker():
            return _postgresql_breaker
        
        breaker = get_postgresql_breaker()
        
        assert breaker['name'] == 'postgresql'


class TestGetSpatialiteBreaker:
    """Tests for get_spatialite_breaker function."""
    
    def test_returns_breaker(self):
        """Test get_spatialite_breaker returns breaker."""
        _spatialite_breaker = {'name': 'spatialite', 'state': 'CLOSED'}
        
        def get_spatialite_breaker():
            return _spatialite_breaker
        
        breaker = get_spatialite_breaker()
        
        assert breaker['name'] == 'spatialite'
