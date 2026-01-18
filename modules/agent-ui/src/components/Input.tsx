import React from "react";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
};

const Input: React.FC<InputProps> = ({ label, hint, className = "", ...props }) => {
  return (
    <label className="field">
      {label ? <span className="field-label">{label}</span> : null}
      <input className={`input ${className}`} {...props} />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
};

export default Input;
