"""Pure rules for handling Streamlit chart selections without sticky state."""

def chart_selection_action(selected, last_seen, current_filter):
    """Apply only a NEW nonempty click, not stale chart selection state."""
    if selected is None or selected == last_seen or selected == current_filter:
        return 'ignore'
    return 'apply'
