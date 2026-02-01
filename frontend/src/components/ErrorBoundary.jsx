import { Component } from 'react';
import logger from '../utils/logger';

/**
 * Error boundary component that catches React errors and logs them.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    logger.error(`React error in ${this.props.name || 'unknown component'}`, {
      component: this.props.name,
      error,
      extra: {
        componentStack: errorInfo.componentStack,
      },
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>An error occurred in this component. Please try refreshing the page.</p>
          {import.meta.env.DEV && <pre>{this.state.error?.toString()}</pre>}
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
