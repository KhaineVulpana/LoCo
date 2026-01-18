import React from "react";

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  hint?: string;
};

const Textarea: React.FC<TextareaProps> = ({ label, hint, className = "", ...props }) => {
  return (
    <label className="field">
      {label ? <span className="field-label">{label}</span> : null}
      <textarea className={`input textarea ${className}`} {...props} />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
};

export default Textarea;
