from agent_blackbox_recorder import Recorder
import tempfile
import shutil

def test_span_context():
    print("Testing span context manager...", end=" ")
    tmpdir = tempfile.mkdtemp()
    try:
        recorder = Recorder(storage=tmpdir)
        recorder.start_session(name="test_session")
        
        with recorder.span("my_span") as span:
            span.set_input({"key": "value"})
            span.set_output({"result": 42})
        
        # Logic from fix: check storage
        sessions = recorder.list_sessions()
        if len(sessions) != 1:
            print("FAIL: Expected 1 session, got", len(sessions))
            return False
            
        session = recorder.load_session(sessions[0]["id"])
        if len(session.events) != 1:
            print("FAIL: Expected 1 event, got", len(session.events))
            return False
            
        if session.events[0].name != "my_span":
            print("FAIL: Expected event name 'my_span', got", session.events[0].name)
            return False
            
        print("PASS")
        return True
    finally:
        shutil.rmtree(tmpdir)

def test_nested():
    print("Testing nested spans...", end=" ")
    tmpdir = tempfile.mkdtemp()
    try:
        recorder = Recorder(storage=tmpdir)
        recorder.start_session(name="test_session")
        
        with recorder.span("outer") as outer:
            with recorder.span("inner") as inner:
                pass
        
        if recorder.current_session is not None:
             print("FAIL: Expected current_session to be None (auto-closed)")
             return False

        sessions = recorder.list_sessions()
        if len(sessions) != 1:
             print("FAIL: Expected 1 session, got", len(sessions))
             return False
             
        session = recorder.load_session(sessions[0]["id"])
        if len(session.events) != 2:
             print("FAIL: Expected 2 events, got", len(session.events))
             return False
             
        print("PASS")
        return True
    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    r1 = test_span_context()
    r2 = test_nested()
    if r1 and r2:
        print("ALL CHECKS PASSED")
        exit(0)
    else:
        print("CHECKS FAILED")
        exit(1)
