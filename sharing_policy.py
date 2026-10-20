"""Versioned sharing choices, separate from upload capability and server authorization."""
POLICY_VERSION = '2026-10-20-sharing-v2'
SCOPES = ('none', 'non_typing', 'including_typing')

def choices(body):
    if body.get('policy_version') != POLICY_VERSION or body.get('acknowledged') is not True:
        raise ValueError('Review the current privacy and sharing notice.')
    scope = body.get('sharing_scope')
    if scope not in SCOPES or body.get('sharing_choices_reviewed') is not True:
        raise ValueError('Choose what to share, including the option to keep everything local.')
    return {'policy_version': POLICY_VERSION, 'acknowledged': True,
            'sharing_scope': scope, 'sharing_choices_reviewed': True,
            'typing_risk_acknowledged': scope == 'including_typing',
            'erp_policy': 'erp-sharing-v1', 'erp_auto_share': scope != 'none',
            'erp_sharing_requested': scope != 'none',
            'decoder_interest_requested': scope == 'including_typing'}
