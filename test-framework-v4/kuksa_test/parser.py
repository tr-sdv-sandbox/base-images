"""
Parsers for VFF specifications and test definitions.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from .models import (
    Signal, SignalType, SignalDirection, ActuatorMode,
    Requirement, RequirementType,
    StateMachine, StateTransition,
    AutosarInterface, VFFSpec,
    TestCase, TestStep, TestStepType, TestSuite,
    Fixture, FixtureType
)


logger = logging.getLogger(__name__)


class SpecParser:
    """Parser for Vehicle Function Framework specifications"""
    
    @staticmethod
    def from_file(filepath: Union[str, Path]) -> VFFSpec:
        """Load VFF specification from YAML file"""
        filepath = Path(filepath)
        
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
            
        return SpecParser.from_dict(data)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> VFFSpec:
        """Parse VFF specification from dictionary"""
        
        # Parse metadata
        metadata = data.get('metadata', {})
        version = data.get('version', '1.0')
        
        # Create spec
        spec = VFFSpec(version=version, metadata=metadata)
        
        # Parse signals
        for signal_data in data.get('signals', []):
            signal = SpecParser._parse_signal(signal_data)
            spec.signals[signal.path] = signal
            
        # Parse requirements
        for req_data in data.get('requirements', []):
            req = SpecParser._parse_requirement(req_data)
            spec.requirements[req.id] = req
            
        # Parse state machines
        for sm_data in data.get('state_machines', []):
            sm = SpecParser._parse_state_machine(sm_data)
            spec.state_machines[sm.name] = sm
            
        # Parse AUTOSAR interfaces
        for interface_data in data.get('autosar_interfaces', []):
            interface = SpecParser._parse_autosar_interface(interface_data)
            spec.autosar_interfaces.append(interface)
            
        return spec
    
    @staticmethod
    def _parse_signal(data: Dict[str, Any]) -> Signal:
        """Parse signal definition"""
        # Parse signal type
        signal_type = SignalType(data['type'])
        
        # Parse direction if present
        direction = None
        if 'direction' in data:
            direction = SignalDirection(data['direction'])
            
        # Parse actuator modes
        mode = None
        if 'mode' in data:
            if isinstance(data['mode'], list):
                mode = [ActuatorMode(m) for m in data['mode']]
            else:
                mode = [ActuatorMode(data['mode'])]
                
        return Signal(
            path=data['path'],
            type=signal_type,
            datatype=data['datatype'],
            direction=direction,
            unit=data.get('unit'),
            min=data.get('min'),
            max=data.get('max'),
            mode=mode,
            enum_values=data.get('enum_values'),
            description=data.get('description')
        )
    
    @staticmethod
    def _parse_requirement(data: Dict[str, Any]) -> Requirement:
        """Parse requirement definition"""
        # Parse requirement type
        req_type = RequirementType(data['type'])
        
        return Requirement(
            id=data['id'],
            text=data['text'],
            type=req_type,
            tags=data.get('tags', []),
            verification=data.get('verification')
        )
    
    @staticmethod
    def _parse_state_machine(data: Dict[str, Any]) -> StateMachine:
        """Parse state machine definition"""
        sm = StateMachine(
            name=data['name'],
            states=data['states'],
            initial_state=data.get('initial_state', data['states'][0])
        )
        
        # Parse transitions
        for trans_data in data.get('transitions', []):
            transition = StateTransition(
                from_state=trans_data['from'],
                to_state=trans_data['to'],
                trigger=trans_data['trigger'],
                condition=trans_data.get('condition'),
                action=trans_data.get('action'),
                requirements=trans_data.get('requirements', [])
            )
            sm.transitions.append(transition)
            
        # Parse substates (hierarchical)
        if 'substates' in data:
            sm.substates = data['substates']
            
        return sm
    
    @staticmethod
    def _parse_autosar_interface(data: Dict[str, Any]) -> AutosarInterface:
        """Parse AUTOSAR interface definition"""
        return AutosarInterface(
            name=data['name'],
            direction=data['direction'],
            signals=data['signals'],
            description=data.get('description')
        )


class TestParser:
    """Parser for test specifications"""
    
    @staticmethod
    def from_file(filepath: Union[str, Path]) -> TestSuite:
        """Load test suite from YAML file"""
        filepath = Path(filepath)
        
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
            
        return TestParser.from_dict(data)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> TestSuite:
        """Parse test suite from dictionary"""
        suite_data = data.get('test_suite', data)

        suite = TestSuite(
            name=suite_data.get('name', 'Test Suite'),
            system_spec=suite_data.get('system_spec'),
            metadata=suite_data.get('metadata', {})
        )

        # Parse fixtures
        if 'fixtures' in suite_data:
            suite.fixtures = TestParser._parse_fixtures(suite_data['fixtures'])

        # Parse setup steps
        if 'setup' in suite_data:
            suite.setup = TestParser._parse_steps(suite_data['setup'])

        # Parse test cases
        for case_data in suite_data.get('test_cases', []):
            test_case = TestParser._parse_test_case(case_data)
            suite.test_cases.append(test_case)

        # Parse teardown steps
        if 'teardown' in suite_data:
            suite.teardown = TestParser._parse_steps(suite_data['teardown'])

        return suite
    
    @staticmethod
    def _parse_test_case(data: Dict[str, Any]) -> TestCase:
        """Parse individual test case"""
        test_case = TestCase(
            name=data['name'],
            description=data.get('description'),
            requirements=data.get('requirements', []),
            tags=data.get('tags', [])
        )
        
        # Parse setup steps
        if 'setup' in data:
            test_case.setup = TestParser._parse_steps(data['setup'])
            
        # Parse main steps
        if 'steps' in data:
            test_case.steps = TestParser._parse_steps(data['steps'])
            
        # Parse teardown steps
        if 'teardown' in data:
            test_case.teardown = TestParser._parse_steps(data['teardown'])
            
        return test_case

    @staticmethod
    def _parse_fixtures(fixtures_data: List[Dict[str, Any]]) -> List[Fixture]:
        """Parse fixtures from YAML data"""
        fixtures = []

        for fixture_data in fixtures_data:
            fixture_type_str = fixture_data.get('type', 'actuator_mirror')

            # Map string to enum
            try:
                fixture_type = FixtureType(fixture_type_str)
            except ValueError:
                logger.warning(f"Unknown fixture type: {fixture_type_str}, skipping")
                continue

            fixture = Fixture(
                name=fixture_data.get('name', f'Fixture {len(fixtures)}'),
                type=fixture_type,
                config={}
            )

            # Copy all config fields except name and type
            for key, value in fixture_data.items():
                if key not in ('name', 'type'):
                    fixture.config[key] = value

            fixtures.append(fixture)
            logger.debug(f"Parsed fixture: {fixture.name} ({fixture.type.value})")

        return fixtures

    @staticmethod
    def _parse_steps(steps_data: List[Any]) -> List[TestStep]:
        """Parse test steps"""
        steps = []
        
        for item in steps_data:
            if isinstance(item, dict):
                # Handle setup/teardown format with 'actions' array
                if 'actions' in item:
                    # Extract steps from actions array
                    for action in item.get('actions', []):
                        step = TestParser._parse_step(action)
                        if step:
                            # Use the parent description if available
                            if not step.description and 'description' in item:
                                step.description = item['description']
                            steps.append(step)
                else:
                    # Direct step format
                    step = TestParser._parse_step(item)
                    if step:
                        steps.append(step)
                    
        return steps
    
    @staticmethod
    def _parse_step(data: Dict[str, Any]) -> Optional[TestStep]:
        """Parse single test step"""
        
        # Determine step type
        step_type = None
        step_data = {}
        timeout = data.get('timeout', 5.0)
        description = data.get('description')
        
        # inject step
        if 'inject' in data:
            step_type = TestStepType.INJECT
            inject_data = data['inject']
            # Handle both single signal and multiple signals format
            if 'path' in inject_data and 'value' in inject_data:
                # Single signal format with optional actuator_mode
                value_dict = {'value': inject_data['value']}
                if 'actuator_mode' in inject_data:
                    value_dict['mode'] = inject_data['actuator_mode']
                step_data['signals'] = {inject_data['path']: value_dict}
            else:
                # Multiple signals format
                step_data['signals'] = inject_data
            
        # expect step
        elif 'expect' in data:
            step_type = TestStepType.EXPECT
            step_data['expectations'] = data['expect']
            
        # expect_state step
        elif 'expect_state' in data:
            step_type = TestStepType.EXPECT_STATE
            state_data = data['expect_state']
            step_data['machine'] = state_data['machine']
            step_data['state'] = state_data['state']
            timeout = state_data.get('timeout', timeout)

        # expect_transition step
        elif 'expect_transition' in data:
            step_type = TestStepType.EXPECT_TRANSITION
            trans_data = data['expect_transition']
            step_data['machine'] = trans_data['machine']
            step_data['from'] = trans_data['from']
            step_data['to'] = trans_data['to']
            step_data['trigger'] = trans_data.get('trigger')  # Optional
            timeout = trans_data.get('timeout', timeout)

        # wait step
        elif 'wait' in data:
            step_type = TestStepType.WAIT
            if isinstance(data['wait'], (int, float)):
                step_data['duration'] = data['wait']
            else:
                step_data['duration'] = float(data['wait'].rstrip('s'))
                
        # log step
        elif 'log' in data:
            step_type = TestStepType.LOG
            step_data['message'] = data['log']
            
        # expect_log step
        elif 'expect_log' in data:
            step_type = TestStepType.EXPECT_LOG
            log_data = data['expect_log']
            if isinstance(log_data, str):
                step_data['pattern'] = log_data
                step_data['container'] = None
            else:
                step_data['pattern'] = log_data.get('pattern', log_data.get('contains'))
                step_data['container'] = log_data.get('container')
                step_data['timeout'] = log_data.get('timeout', timeout)
                
        # run step
        elif 'run' in data:
            step_type = TestStepType.RUN
            step_data['command'] = data['run']
            
        else:
            logger.warning(f"Unknown step type: {list(data.keys())}")
            return None
            
        return TestStep(
            type=step_type,
            data=step_data,
            timeout=timeout,
            description=description
        )


class ConfigLoader:
    """Load test configuration from files"""
    
    @staticmethod
    def load_test_config(config_file: Union[str, Path]) -> Dict[str, Any]:
        """Load test configuration including spec and test paths"""
        config_file = Path(config_file)
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            
        # Resolve relative paths
        base_dir = config_file.parent
        
        if 'spec_file' in config:
            config['spec_file'] = base_dir / config['spec_file']
            
        if 'test_file' in config:
            config['test_file'] = base_dir / config['test_file']
            
        if 'test_files' in config:
            config['test_files'] = [base_dir / f for f in config['test_files']]
            
        return config