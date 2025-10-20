import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../../src/App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByTestId('app')).toBeInTheDocument();
  });
  
  it('displays app title', () => {
    render(<App />);
    expect(screen.getByText(/Arkham Assistant/i)).toBeInTheDocument();
  });
});

