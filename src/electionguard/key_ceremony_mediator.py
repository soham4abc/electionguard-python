from typing import Dict, Iterable, List, NamedTuple, Optional
from .key_ceremony import (
    AuxiliaryPublicKey,
    CeremonyDetails,
    ElectionJointKey,
    ElectionPartialKeyBackup,
    ElectionPartialKeyChallenge,
    ElectionPartialKeyVerification,
    ElectionPublicKey,
    PublicKeySet,
    combine_election_public_keys,
    verify_election_partial_key_challenge,
)
from .type import GUARDIAN_ID, MEDIATOR_ID


class GuardianPair(NamedTuple):
    """Pair of guardians involved in sharing"""

    owner_id: GUARDIAN_ID
    designated_id: GUARDIAN_ID


class BackupVerificationState(NamedTuple):
    """The state of the verifications of all guardian election partial key backups"""

    all_sent: bool = False
    all_verified: bool = False
    failed_verifications: List[GuardianPair] = []


class KeyCeremonyMediator:
    """
    KeyCeremonyMediator for assisting communication between guardians
    """

    id: MEDIATOR_ID
    ceremony_details: CeremonyDetails

    # From Guardians
    # Round 1
    _auxiliary_public_keys: Dict[GUARDIAN_ID, AuxiliaryPublicKey]
    _election_public_keys: Dict[GUARDIAN_ID, ElectionPublicKey]

    # Round 2
    _election_partial_key_backups: Dict[GuardianPair, ElectionPartialKeyBackup]

    # Round 3
    _election_partial_key_verifications: Dict[
        GuardianPair, ElectionPartialKeyVerification
    ]

    def __init__(self, id: MEDIATOR_ID, ceremony_details: CeremonyDetails):
        self.id = id
        self.ceremony_details = ceremony_details
        self._auxiliary_public_keys: Dict[GUARDIAN_ID, AuxiliaryPublicKey] = {}
        self._election_public_keys: Dict[GUARDIAN_ID, ElectionPublicKey] = {}
        self._election_partial_key_backups: Dict[
            GuardianPair, ElectionPartialKeyBackup
        ] = {}
        self._election_partial_key_verifications: Dict[
            GuardianPair, ElectionPartialKeyVerification
        ] = {}
        self._election_partial_key_challenges: Dict[
            GuardianPair, ElectionPartialKeyChallenge
        ] = {}

    # ROUND 1: Announce guardians with public keys
    def announce(self, public_key_set: PublicKeySet) -> None:
        """
        Announce the guardian as present and participating the Key Ceremony
        :param public_key_set: Both the guardians public keys
        """
        self._receive_election_public_key(public_key_set.election)
        self._receive_auxiliary_public_key(public_key_set.auxiliary)

    def all_guardians_announced(self) -> bool:
        """
        Check the annoucement of all the guardians expected
        :return: True if all guardians in attendance are announced
        """
        return (
            self._all_auxiliary_public_keys_available()
            and self._all_election_public_keys_available()
        )

    def share_announced(
        self, requesting_guardian_id: Optional[GUARDIAN_ID] = None
    ) -> Optional[List[PublicKeySet]]:
        """
        When all guardians have announced, share their public keys indicating their announcement
        """
        if not self.all_guardians_announced():
            return None

        guardian_keys: List[PublicKeySet] = []
        for guardian_id in self._get_announced_guardians():
            if guardian_id is not requesting_guardian_id:
                guardian_keys.append(
                    PublicKeySet(
                        self._election_public_keys[guardian_id],
                        self._auxiliary_public_keys[guardian_id],
                    )
                )
        return guardian_keys

    # ROUND 2: Share Election Partial Key Backups for compensating
    def receive_backups(self, backups: List[ElectionPartialKeyBackup]) -> None:
        """
        Receive all the election partial key backups generated by a guardian
        """
        if not self.all_guardians_announced():
            return
        for backup in backups:
            self._receive_election_partial_key_backup(backup)

    def all_backups_available(self) -> bool:
        """
        Check the availability of all the guardians backups
        :return: True if all guardians have sent backups
        """
        return (
            self.all_guardians_announced()
            and self._all_election_partial_key_backups_available()
        )

    def share_backups(
        self, requesting_guardian_id: Optional[GUARDIAN_ID] = None
    ) -> Optional[List[ElectionPartialKeyBackup]]:
        """
        Share all backups designated for a specific guardian
        """
        if not self.all_guardians_announced() or not self.all_backups_available:
            return None
        if not requesting_guardian_id:
            return list(self._election_partial_key_backups.values())
        return self._share_election_partial_key_backups_to_guardian(
            requesting_guardian_id
        )

    # ROUND 3: Share verifications of backups
    def receive_backup_verifications(
        self, verifications: List[ElectionPartialKeyVerification]
    ) -> None:
        """
        Receive all the election partial key verifications performed by a guardian
        """
        if not self.all_backups_available():
            return
        for verification in verifications:
            self._receive_election_partial_key_verification(verification)

    def get_verification_state(self) -> BackupVerificationState:
        if (
            not self.all_backups_available()
            or not self._all_election_partial_key_verifications_received()
        ):
            return BackupVerificationState()
        return self._check_verification_of_election_partial_key_backups()

    def all_backups_verified(self) -> bool:
        return self.get_verification_state().all_verified

    # ROUND 4 (Optional): If a verification fails, guardian must issue challenge
    def verify_challenge(
        self, challenge: ElectionPartialKeyChallenge
    ) -> ElectionPartialKeyVerification:
        """
        Mediator receives challenge and will act to mediate and verify
        """
        verification = verify_election_partial_key_challenge(self.id, challenge)
        if verification.verified:
            self._receive_election_partial_key_verification(verification)
        return verification

    # FINAL: Publish joint public election key
    def publish_joint_key(self) -> Optional[ElectionJointKey]:
        """
        Publish joint election key from the public keys of all guardians
        :return: Joint key for election
        """
        if not self.all_backups_verified():
            return None

        return combine_election_public_keys(list(self._election_public_keys.values()))

    def reset(self, ceremony_details: CeremonyDetails) -> None:
        """
        Reset mediator to initial state
        :param ceremony_details: Ceremony details of election
        """
        self.ceremony_details = ceremony_details
        self._auxiliary_public_keys = {}
        self._election_public_keys = {}
        self._election_partial_key_backups = {}
        self._election_partial_key_challenges = {}
        self._election_partial_key_verifications = {}

    # Auxiliary Public Keys
    def _receive_auxiliary_public_key(self, public_key: AuxiliaryPublicKey) -> None:
        """
        Receive auxiliary public key from guardian
        :param public_key: Auxiliary public key
        """
        self._auxiliary_public_keys[public_key.owner_id] = public_key

    def _all_auxiliary_public_keys_available(self) -> bool:
        """
        True if all auxiliary public key for all guardians available
        :return: All auxiliary public backups for all guardians available
        """
        return (
            len(self._auxiliary_public_keys)
            == self.ceremony_details.number_of_guardians
        )

    # Election Public Keys
    def _receive_election_public_key(self, public_key: ElectionPublicKey) -> None:
        """
        Receive election public key from guardian
        :param public_key: election public key
        """
        self._election_public_keys[public_key.owner_id] = public_key

    def _all_election_public_keys_available(self) -> bool:
        """
        True if all election public keys for all guardians available
        :return: All election public keys for all guardians available
        """
        return (
            len(self._election_public_keys) == self.ceremony_details.number_of_guardians
        )

    def _get_announced_guardians(self) -> Iterable[GUARDIAN_ID]:
        return self._election_public_keys.keys()

    # Election Partial Key Backups
    def _receive_election_partial_key_backup(
        self, backup: ElectionPartialKeyBackup
    ) -> None:
        """
        Receive election partial key backup from guardian
        :param backup: Election partial key backup
        :return: boolean indicating success or failure
        """
        if backup.owner_id == backup.designated_id:
            return
        self._election_partial_key_backups[
            GuardianPair(backup.owner_id, backup.designated_id)
        ] = backup

    def _all_election_partial_key_backups_available(self) -> bool:
        """
        True if all election partial key backups for all guardians available
        :return: All election partial key backups for all guardians available
        """
        required_backups_per_guardian = self.ceremony_details.number_of_guardians - 1
        return (
            len(self._election_partial_key_backups)
            == required_backups_per_guardian * self.ceremony_details.number_of_guardians
        )

    def _share_election_partial_key_backups_to_guardian(
        self, guardian_id: GUARDIAN_ID
    ) -> List[ElectionPartialKeyBackup]:
        """
        Share all election partial key backups for designated guardian
        :param guardian_id: Recipients guardian id
        :return: List of guardians designated backups
        """
        backups: List[ElectionPartialKeyBackup] = []
        for current_guardian_id in self._get_announced_guardians():
            if guardian_id != current_guardian_id:
                backup = self._election_partial_key_backups[
                    GuardianPair(current_guardian_id, guardian_id)
                ]
                if backup is not None:
                    backups.append(backup)
        return backups

    # Partial Key Verifications
    def _receive_election_partial_key_verification(
        self, verification: ElectionPartialKeyVerification
    ) -> None:
        """
        Receive election partial key verification from guardian
        :param verification: Election partial key verification
        """
        if verification.owner_id == verification.designated_id:
            return
        self._election_partial_key_verifications[
            GuardianPair(verification.owner_id, verification.designated_id)
        ] = verification

    def _all_election_partial_key_verifications_received(self) -> bool:
        """
        True if all election partial key verifications recieved
        :return: All election partial key verifications received
        """
        required_verifications_per_guardian = (
            self.ceremony_details.number_of_guardians - 1
        )
        return (
            len(self._election_partial_key_verifications)
            == required_verifications_per_guardian
            * self.ceremony_details.number_of_guardians
        )

    def _check_verification_of_election_partial_key_backups(
        self,
    ) -> BackupVerificationState:
        """
        True if all election partial key backups verified
        :return: All election partial key backups verified
        """
        if not self._all_election_partial_key_verifications_received():
            return BackupVerificationState()
        failed_verifications: List[GuardianPair] = []
        for verification in self._election_partial_key_verifications.values():
            if not verification.verified:
                failed_verifications.append(
                    GuardianPair(verification.owner_id, verification.designated_id)
                )

        return BackupVerificationState(
            True, len(failed_verifications) == 0, failed_verifications
        )
