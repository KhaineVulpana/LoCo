import React from "react";

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  hint?: string;
};

const Select: React.FC<SelectProps> = ({ label, hint, className = "", children, ...props }) => {
  return (
    <label className="field">
      {label ? <span className="field-label">{label}</span> : null}
      <select className={`input select ${className}`} {...props}>
        {children}
      </select>
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
};

export default Select;
