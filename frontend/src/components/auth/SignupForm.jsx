import React from 'react';
import { FormInput, MultiSelect, MailIcon, LockIcon, UserIcon, Loader2Icon } from '../ui';
import RoleSwitcher from './RoleSwitcher';
import { ROLE } from '../../utilities/constants';

/**
 * Signup form: role switcher (Student/Mentor) then either student fields or mentor fields.
 */
function SignupForm({
  role,
  onRoleChange,
  roleLocked,
  // Student fields
  firstName,
  lastName,
  studentEmail,
  studentUsername,
  studentPassword,
  studentConfirmPassword,
  targetDomainIds,
  domains,
  domainsLoading,
  domainsError,
  onFirstNameChange,
  onLastNameChange,
  onStudentEmailChange,
  onStudentUsernameChange,
  onStudentPasswordChange,
  onStudentConfirmPasswordChange,
  onTargetDomainIdsChange,
  // Mentor fields
  mentorEmail,
  mentorUsername,
  mentorPassword,
  mentorConfirmPassword,
  professionalBio,
  expertiseDomainId,
  onMentorEmailChange,
  onMentorUsernameChange,
  onMentorPasswordChange,
  onMentorConfirmPasswordChange,
  onProfessionalBioChange,
  onExpertiseDomainIdChange,
  loading,
  onSubmit,
  onSwitchToLogin,
  accentClass = 'text-blue-600 hover:text-blue-700',
  buttonClass = 'bg-blue-600 hover:bg-blue-700',
}) {
  const selectClass =
    'w-full px-3 py-2.5 rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none disabled:opacity-50';

  return (
    <>
      {!roleLocked && <RoleSwitcher role={role} onRoleChange={onRoleChange} />}

      <form onSubmit={onSubmit} className="space-y-5 mt-6">
        {/* Student fields */}
        {role === ROLE.STUDENT && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <FormInput
                id="first-name"
                label="First Name"
                placeholder="John"
                value={firstName}
                onChange={(e) => onFirstNameChange(e.target.value)}
                required
                disabled={loading}
              />
              <FormInput
                id="last-name"
                label="Last Name"
                placeholder="Doe"
                value={lastName}
                onChange={(e) => onLastNameChange(e.target.value)}
                required
                disabled={loading}
              />
            </div>
            <FormInput
              id="student-email"
              label="Email"
              type="email"
              placeholder="john@example.com"
              value={studentEmail}
              onChange={(e) => onStudentEmailChange(e.target.value)}
              required
              disabled={loading}
              icon={MailIcon}
            />
            <FormInput
              id="student-username"
              label="Username"
              placeholder="johndoe"
              value={studentUsername}
              onChange={(e) => onStudentUsernameChange(e.target.value)}
              required
              disabled={loading}
              icon={UserIcon}
            />
            <FormInput
              id="student-password"
              label="Password"
              type="password"
              placeholder="Min 8 characters"
              value={studentPassword}
              onChange={(e) => onStudentPasswordChange(e.target.value)}
              required
              disabled={loading}
              minLength={8}
              icon={LockIcon}
              showPasswordToggle
            />
            <FormInput
              id="student-confirm-password"
              label="Confirm Password"
              type="password"
              placeholder="Confirm password"
              value={studentConfirmPassword}
              onChange={(e) => onStudentConfirmPasswordChange(e.target.value)}
              required
              disabled={loading}
              icon={LockIcon}
              showPasswordToggle
            />
            <div>
              <label className="block text-gray-700 text-sm font-medium mb-1">Target Domains (select 2–3)</label>
              <MultiSelect
                options={domains}
                value={targetDomainIds}
                onChange={onTargetDomainIdsChange}
                placeholder={domainsLoading ? 'Loading domains…' : 'Select 2 to 3 areas of interest'}
                disabled={loading || domainsLoading}
                maxSelected={3}
              />
              {domainsError && (
                <p className="mt-1 text-red-600 text-xs">
                  {domainsError?.response?.data?.detail || domainsError?.message || (typeof domainsError === 'string' ? domainsError : 'Failed to load domains. Check your connection and try again.')}
                </p>
              )}
              {!domainsLoading && !domainsError && domains.length === 0 && (
                <p className="mt-1 text-amber-600 text-xs">No domains loaded. Run: python manage.py populate_domains (in backend).</p>
              )}
            </div>
          </>
        )}

        {/* Mentor fields */}
        {role === ROLE.MENTOR && (
          <>
            <FormInput
              id="mentor-email"
              label="Email"
              type="email"
              placeholder="mentor@example.com"
              value={mentorEmail}
              onChange={(e) => onMentorEmailChange(e.target.value)}
              required
              disabled={loading}
              icon={MailIcon}
            />
            <FormInput
              id="mentor-username"
              label="Username"
              placeholder="Choose a username (e.g. jane_smith)"
              value={mentorUsername}
              onChange={(e) => onMentorUsernameChange(e.target.value)}
              required
              disabled={loading}
              icon={UserIcon}
            />
            <FormInput
              id="mentor-password"
              label="Password"
              type="password"
              placeholder="Min 8 characters"
              value={mentorPassword}
              onChange={(e) => onMentorPasswordChange(e.target.value)}
              required
              disabled={loading}
              minLength={8}
              icon={LockIcon}
              showPasswordToggle
            />
            <FormInput
              id="mentor-confirm-password"
              label="Confirm Password"
              type="password"
              placeholder="Confirm password"
              value={mentorConfirmPassword}
              onChange={(e) => onMentorConfirmPasswordChange(e.target.value)}
              required
              showPasswordToggle
              disabled={loading}
              icon={LockIcon}
            />
            <div>
              <label htmlFor="professional-bio" className="block text-gray-700 text-sm font-medium mb-1">
                Professional Bio
              </label>
              <textarea
                id="professional-bio"
                placeholder="Your background, expertise, and how you mentor (e.g. 5+ years in web dev)"
                value={professionalBio}
                onChange={(e) => onProfessionalBioChange(e.target.value)}
                className={selectClass + ' min-h-[100px]'}
                required
                disabled={loading}
              />
            </div>
            <div>
              <label htmlFor="expertise-domain" className="block text-gray-700 text-sm font-medium mb-1">
                Expertise Domain
              </label>
              <select
                id="expertise-domain"
                value={expertiseDomainId}
                onChange={(e) => onExpertiseDomainIdChange(e.target.value)}
                className={selectClass}
                required
                disabled={loading || domainsLoading}
              >
                <option value="">Select domain</option>
                {domains.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        <button
          type="submit"
          className={`w-full py-3 rounded-lg ${buttonClass} text-white font-medium disabled:opacity-70 flex items-center justify-center gap-2`}
          disabled={loading || (role === ROLE.STUDENT && domainsLoading)}
        >
          {loading ? (
            <>
              <Loader2Icon className="w-4 h-4 animate-spin" />
              Creating account...
            </>
          ) : (
            'Create Account'
          )}
        </button>
      </form>

      <p className="text-center text-gray-600 text-sm mt-6">
        Already have an account?{' '}
        <button type="button" className={`font-medium ${accentClass}`} onClick={onSwitchToLogin}>
          Log in
        </button>
      </p>
    </>
  );
}

export default SignupForm;
